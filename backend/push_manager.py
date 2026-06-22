"""推送管理模块

提供消息推送配置管理、事件推送处理器和事件 API 路由。
从 main.py 拆分出来以保持代码组织清晰。
"""

import json
import re
import time
import requests
from pathlib import Path
from typing import Dict, Any, List

from flask import request, render_template
from event_bus import event_bus, Event, EventType, fire_event, get_events_catalog


# ==================== 推送服务器预设 ====================

PUSH_SERVER_PRESETS = {
    'magicpush': {
        'name': 'MagicPush',
        'paramMapping': [
            {'from': 'title', 'to': 'title'},
            {'from': 'content', 'to': 'content'},
            {'from': 'type', 'to': 'type'},
        ],
        'urlTemplate': '',
        'expectedStatus': 200,
    },
    'bark': {
        'name': 'Bark',
        'paramMapping': [
            {'from': 'title', 'to': 'title'},
            {'from': 'content', 'to': 'body'},
            {'from': 'type', 'to': 'level'},
        ],
        'urlTemplate': 'https://api.day.app/{token}',
        'expectedStatus': 200,
    },
    'serverchan': {
        'name': 'Server酱',
        'paramMapping': [
            {'from': 'title', 'to': 'title'},
            {'from': 'content', 'to': 'desp'},
        ],
        'urlTemplate': 'https://sctapi.ftqq.com/{token}.send',
        'expectedStatus': 200,
    },
    'pushplus': {
        'name': 'PushPlus',
        'paramMapping': [
            {'from': 'title', 'to': 'title'},
            {'from': 'content', 'to': 'content'},
            {'from': 'type', 'to': 'template'},
        ],
        'urlTemplate': '',
        'expectedStatus': 200,
    },
    'custom': {
        'name': '自定义',
        'paramMapping': [],
        'urlTemplate': '',
        'expectedStatus': 200,
    },
}


try:
    from auth import get_current_user, get_user_config_path
except ImportError:
    def get_current_user():
        return None
    def get_user_config_path(username, name):
        return Path('config') / name


def _get_push_config_path() -> str:
    """获取用户专属推送配置文件路径"""
    username = get_current_user()
    if username:
        return str(get_user_config_path(username, 'push_config.json'))
    return str(Path('config') / 'push_config.json')


def _load_push_config() -> Dict[str, Any]:
    """加载推送配置（用户专属）"""
    config_path = _get_push_config_path()
    if Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    return {'pushes': []}


def _iter_all_push_configs() -> List[Dict[str, Any]]:
    """加载所有用户 + 全局的推送配置

    事件常在后台/异步线程触发（下载、同步），此时无 Flask 请求上下文，
    get_current_user() 取不到用户，导致只能读到全局配置而漏掉用户专属配置。
    事件处理器改为遍历全部配置，确保任意线程下都能正确推送。
    """
    project_root = Path(__file__).resolve().parent.parent
    candidates = [project_root / 'config' / 'push_config.json']

    users_dir = project_root / 'config' / 'users'
    if users_dir.exists():
        for user_dir in users_dir.iterdir():
            if user_dir.is_dir():
                candidates.append(user_dir / 'push_config.json')

    configs: List[Dict[str, Any]] = []
    seen = set()
    for path in candidates:
        key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                configs.append(json.load(f))
        except Exception:
            continue
    return configs


def _save_push_config(data: Dict[str, Any]) -> None:
    """保存推送配置（用户专属）"""
    config_path = _get_push_config_path()
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _send_push_to_url(url: str, payload: Dict[str, Any],
                      expected_status: int = 200) -> bool:
    """发送推送消息到指定 URL

    Args:
        url: 推送目标 URL
        payload: 请求体（JSON）
        expected_status: 期望的 HTTP 状态码，默认 200

    Returns:
        是否发送成功
    """
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == expected_status
    except Exception:
        return False


def _resolve_url(base_url: str, fixed_params: Dict[str, str],
                 url_override: str = '') -> str:
    """解析 URL 模板，替换 {key} 占位符

    Args:
        base_url: URL 模板，如 'https://api.day.app/{token}'
        fixed_params: 固定参数字典
        url_override: 覆盖 URL（优先级最高）

    Returns:
        替换后的完整 URL
    """
    url = url_override or base_url
    if not url:
        return ''
    for key, value in fixed_params.items():
        url = url.replace('{' + key + '}', str(value))
    return url


def _build_push_payload(server: Dict[str, Any], title: str,
                        content: str, push_type: str) -> Dict[str, Any]:
    """按服务器 paramMapping 构建请求体

    Args:
        server: 服务器配置（含 paramMapping, fixedParams）
        title: 推送标题
        content: 推送内容
        push_type: 推送类型

    Returns:
        构建好的请求体字典
    """
    payload = {}
    mapping = server.get('paramMapping', [])
    fixed = server.get('fixedParams', {})

    # 先合并固定参数
    payload.update(fixed)

    # 再按映射规则填充动态参数
    value_map = {'title': title, 'content': content, 'type': push_type}
    for m in mapping:
        from_key = m.get('from', '')
        to_key = m.get('to', from_key)
        if from_key in value_map:
            payload[to_key] = value_map[from_key]

    return payload


def _render_template(template: str, event_data: Dict[str, Any]) -> str:
    """渲染消息模板，替换 {变量名} 占位符

    支持两种变量来源：
    1. 事件数据变量：从 event_data 中查找，如 {song_name}、{artist}
    2. 内置变量：系统预定义的变量，如 {now}、{当前时间}
    """
    # 内置变量解析器
    _builtin_vars = {
        'now': lambda: time.strftime('%Y-%m-%d %H:%M:%S'),
        '当前时间': lambda: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def replace_var(match):
        var_name = match.group(1)
        # 优先匹配内置变量
        if var_name in _builtin_vars:
            return _builtin_vars[var_name]()
        # 其次从事件数据中查找
        value = event_data.get(var_name, '')
        return str(value) if value else f'{{{var_name}}}'

    # 正则支持英文字母、数字、下划线及中文字符作为变量名
    return re.sub(r'\{([\w\u4e00-\u9fff]+)\}', replace_var, template)


class PushEventHandler:
    """事件推送处理器

    从 push_config.json 中读取推送配置，检查每个推送的 events 列表。
    如果当前事件在某个推送的 events 中，则使用 event_template 渲染并发送。
    """

    def __init__(self, logger):
        self._logger = logger

    def handle(self, event: Event) -> None:
        """处理事件，匹配推送配置并发送

        支持两种模式：
        1. 服务器模式（push.serverId）：用服务器配置构建 URL + payload
        2. 直连模式（旧，push.urls[]）：直接发送到配置中的 URL
        """
        try:
            event_value = event.type.value
            # 遍历所有用户 + 全局配置（规避后台线程无用户上下文问题）
            pushes = []
            all_servers: Dict[str, Dict[str, Any]] = {}
            for cfg in _iter_all_push_configs():
                pushes.extend(cfg.get('pushes', []))
                for srv in cfg.get('servers', []):
                    if srv.get('id'):
                        all_servers[srv['id']] = srv

            for push in pushes:
                if not push.get('enabled', False):
                    continue
                push_events = push.get('events', [])
                if not push_events or event_value not in push_events:
                    continue

                # 渲染标题/内容
                title, content, push_type = self._resolve_content(push, event)

                server_id = push.get('serverId', '')
                if server_id and server_id in all_servers:
                    # === 服务器模式 ===
                    server = all_servers[server_id]
                    base_url = server.get('baseUrl', '')
                    fixed = server.get('fixedParams', {})
                    expected_status = server.get('expectedStatus', 200)
                    url = _resolve_url(base_url, fixed)
                    if not url:
                        self._logger.warning(
                            f"推送服务器 URL 为空: push={push.get('name', '')}, "
                            f"server={server.get('name', '')}"
                        )
                        continue
                    payload = _build_push_payload(
                        server, title, content, push_type
                    )
                    success = _send_push_to_url(url, payload, expected_status)
                    if success:
                        self._logger.info(
                            f"事件推送成功: event={event_value}, "
                            f"push={push.get('name', '')}, "
                            f"server={server.get('name', '')}, "
                            f"url={url[:50]}..."
                        )
                    else:
                        self._logger.warning(
                            f"事件推送失败: event={event_value}, "
                            f"push={push.get('name', '')}, "
                            f"server={server.get('name', '')}"
                        )
                else:
                    # === 直连模式（兼容旧配置） ===
                    for url_item in push.get('urls', []):
                        if not url_item.get('enabled') or not url_item.get('url'):
                            continue
                        payload = {
                            'title': title, 'content': content, 'type': push_type
                        }
                        success = _send_push_to_url(
                            url_item['url'], payload
                        )
                        if success:
                            self._logger.info(
                                f"事件推送成功(直连): event={event_value}, "
                                f"push={push.get('name', '')}, "
                                f"url={url_item['url'][:50]}..."
                            )
                        else:
                            self._logger.warning(
                                f"事件推送失败(直连): event={event_value}, "
                                f"push={push.get('name', '')}, "
                                f"url={url_item['url'][:50]}..."
                            )
        except Exception as e:
            self._logger.error(f"事件推送处理器异常: {e}")

    def _resolve_content(self, push: dict, event: Event):
        """解析推送内容（模板渲染或固定内容）"""
        tpl = push.get('event_template', {})
        if tpl and tpl.get('title'):
            event_data = event.data.copy()
            event_data['_event_type'] = event.type.value
            event_data['_event_source'] = event.source
            event_data['_timestamp'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp)
            )
            title = _render_template(tpl.get('title', ''), event_data)
            content = _render_template(tpl.get('content', ''), event_data)
            push_type = tpl.get('type', 'text')
        else:
            title = push.get('title', '')
            content = push.get('content', '')
            push_type = push.get('type', 'text')
        return title, content, push_type


def init_push_routes(app, api_service):
    """注册推送管理和事件相关路由到 Flask app"""
    handler = PushEventHandler(api_service.logger)

    # 注册事件推送处理器（订阅所有事件）
    event_bus.subscribe('*', handler.handle)
    api_service.logger.info("事件推送处理器已注册")

    # ==================== 推送配置 API ====================

    @app.route('/api/push/config', methods=['GET'])
    def get_push_config():
        try:
            return api_service.APIResponse.success(
                _load_push_config(), "获取推送配置成功"
            )
        except Exception as e:
            return api_service.APIResponse.error(
                f"获取推送配置失败: {str(e)}", 500
            )

    @app.route('/api/push/config', methods=['POST'])
    def save_push_config():
        try:
            data = api_service._safe_get_request_data()
            _save_push_config(data)
            fire_event(EventType.PUSH_CONFIG_UPDATED, {
                'push_count': len(data.get('pushes', [])),
            }, source='api')
            return api_service.APIResponse.success(None, "推送配置已保存")
        except Exception as e:
            return api_service.APIResponse.error(
                f"保存推送配置失败: {str(e)}", 500
            )

    @app.route('/api/push/send', methods=['POST'])
    def send_push():
        """发送推送消息

        支持两种模式：
        1. serverId 模式：指定服务器 ID，使用服务器配置发送
           { "serverId": "srv_001", "title": "...", "content": "...", "type": "text" }
        2. 直连模式（兼容旧版）：指定 url 直接发送
           { "url": "...", "title": "...", "content": "...", "type": "text" }
        """
        try:
            data = api_service._safe_get_request_data()
            title = data.get('title', '')
            content = data.get('content', '')
            push_type = data.get('type', 'text')
            server_id = data.get('serverId', '')

            # 服务器模式
            if server_id:
                config = _load_push_config()
                servers = config.get('servers', [])
                server = next((s for s in servers if s.get('id') == server_id), None)
                if not server:
                    return api_service.APIResponse.error(
                        f"推送服务器 '{server_id}' 不存在", 400
                    )
                base_url = server.get('baseUrl', '')
                fixed = server.get('fixedParams', {})
                expected_status = server.get('expectedStatus', 200)
                url = _resolve_url(base_url, fixed)
                if not url:
                    return api_service.APIResponse.error("推送服务器 URL 为空", 400)
                payload = _build_push_payload(server, title, content, push_type)
                r = requests.post(url, json=payload, timeout=10)
                if r.status_code == expected_status:
                    return api_service.APIResponse.success(
                        {'status_code': r.status_code, 'server': server.get('name', '')},
                        "推送成功"
                    )
                return api_service.APIResponse.error(
                    f"推送失败: HTTP {r.status_code} {r.text[:200]}", 400
                )

            # 直连模式（兼容旧版）
            url = data.get('url', '').strip()
            if not url:
                return api_service.APIResponse.error("推送URL不能为空", 400)
            payload = {'title': title, 'content': content, 'type': push_type}
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                return api_service.APIResponse.success(
                    {'status_code': r.status_code}, "推送成功"
                )
            return api_service.APIResponse.error(
                f"推送失败: HTTP {r.status_code} {r.text[:200]}", 400
            )
        except requests.exceptions.Timeout:
            return api_service.APIResponse.error("推送超时", 500)
        except requests.exceptions.ConnectionError:
            return api_service.APIResponse.error("无法连接到推送地址", 500)
        except Exception as e:
            return api_service.APIResponse.error(f"推送失败: {str(e)}", 500)

    # ==================== 推送服务器 API ====================

    @app.route('/api/push/servers', methods=['GET'])
    def get_push_servers():
        """获取推送服务器列表"""
        try:
            config = _load_push_config()
            return api_service.APIResponse.success(
                config.get('servers', []), "获取推送服务器列表成功"
            )
        except Exception as e:
            return api_service.APIResponse.error(
                f"获取推送服务器列表失败: {str(e)}", 500
            )

    @app.route('/api/push/servers', methods=['POST'])
    def save_push_servers():
        """保存推送服务器列表"""
        try:
            data = api_service._safe_get_request_data()
            config = _load_push_config()
            config['servers'] = data if isinstance(data, list) else []
            _save_push_config(config)
            return api_service.APIResponse.success(None, "推送服务器配置已保存")
        except Exception as e:
            return api_service.APIResponse.error(
                f"保存推送服务器配置失败: {str(e)}", 500
            )

    @app.route('/api/push/server-presets', methods=['GET'])
    def get_server_presets():
        """获取推送服务器预设类型"""
        try:
            return api_service.APIResponse.success(
                PUSH_SERVER_PRESETS, "获取服务器预设成功"
            )
        except Exception as e:
            return api_service.APIResponse.error(
                f"获取服务器预设失败: {str(e)}", 500
            )

    # ==================== 事件 API ====================

    @app.route('/api/events/catalog', methods=['GET'])
    def api_events_catalog():
        try:
            catalog = get_events_catalog()
            return api_service.APIResponse.success(catalog, "事件目录获取成功")
        except Exception as e:
            return api_service.APIResponse.error(
                f"获取事件目录失败: {str(e)}", 500
            )

    @app.route('/api/events/history', methods=['GET'])
    def api_events_history():
        try:
            event_type_str = request.args.get('type', '')
            limit = int(request.args.get('limit', 50))
            event_type = None
            if event_type_str:
                try:
                    event_type = EventType(event_type_str)
                except ValueError:
                    pass
            history = event_bus.get_history(event_type=event_type, limit=limit)
            return api_service.APIResponse.success(history, "事件历史获取成功")
        except Exception as e:
            return api_service.APIResponse.error(
                f"获取事件历史失败: {str(e)}", 500
            )

    @app.route('/api/events/subscribers', methods=['GET'])
    def api_events_subscribers():
        try:
            subscribers = event_bus.get_subscribers_info()
            return api_service.APIResponse.success(subscribers, "订阅信息获取成功")
        except Exception as e:
            return api_service.APIResponse.error(
                f"获取订阅信息失败: {str(e)}", 500
            )

    api_service.logger.info("推送管理和事件路由已注册")
 
