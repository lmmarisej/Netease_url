"""
Cookie 管理路由
"""

import traceback

from flask import request

from backend.api_core import APIResponse
from backend.event_bus import EventType, fire_event
from backend.auth import get_current_user


def register_cookie_routes(app, api_service, config):
    """注册Cookie相关路由"""

    @app.route('/api/cookie', methods=['GET'])
    def get_cookie_config():
        try:
            username = get_current_user()
            if username:
                from backend.main import _get_user_cookie_path
                api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
            cookies = api_service.cookie_manager.list_cookies()
            active = api_service.cookie_manager.get_active_cookie_name()
            return APIResponse.success({
                'cookies': cookies, 'active': active,
                'content': api_service.cookie_manager.read_cookie(),
            }, "获取Cookie配置成功")
        except Exception as e:
            return APIResponse.error(f"获取Cookie配置失败: {str(e)}", 500)

    @app.route('/api/cookie', methods=['POST'])
    def save_cookie_config():
        try:
            username = get_current_user()
            if username:
                from backend.main import _get_user_cookie_path
                api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
            data = api_service._safe_get_request_data()
            cookie_name = (data.get('name') or '默认').strip()
            cookie_content = (data.get('cookie') or data.get('content') or '').strip()

            if not cookie_content:
                return APIResponse.error("Cookie内容不能为空", 400)

            api_service.cookie_manager.save_named_cookie(cookie_name, cookie_content)

            fire_event(EventType.COOKIE_UPDATED, {
                'name': cookie_name, 'has_content': bool(cookie_content),
            }, source='api')
            return APIResponse.success({'name': cookie_name, 'saved': True},
                                       f"Cookie [{cookie_name}] 保存成功")
        except Exception as e:
            return APIResponse.error(f"保存Cookie配置失败: {str(e)}", 500)

    @app.route('/api/cookie/activate', methods=['POST'])
    def activate_cookie():
        try:
            username = get_current_user()
            if username:
                from backend.main import _get_user_cookie_path
                api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
            data = api_service._safe_get_request_data()
            name = (data.get('name') or '').strip()
            if not name:
                return APIResponse.error("Cookie名称不能为空", 400)
            if api_service.cookie_manager.activate_cookie(name):
                return APIResponse.success({'active': name}, f"已激活 Cookie [{name}]")
            return APIResponse.error(f"Cookie [{name}] 不存在", 404)
        except Exception as e:
            return APIResponse.error(f"激活失败: {str(e)}", 500)

    @app.route('/api/cookie/<name>', methods=['DELETE'])
    def delete_cookie_config(name):
        try:
            username = get_current_user()
            if username:
                from backend.main import _get_user_cookie_path
                api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
            api_service.cookie_manager.delete_cookie(name)
            return APIResponse.success(None, f"Cookie [{name}] 已删除")
        except Exception as e:
            return APIResponse.error(f"删除失败: {str(e)}", 500)

    @app.route('/api/qq/cookie', methods=['GET'])
    def get_qq_cookie_config():
        try:
            from backend.main import _read_qq_cookie
            content = _read_qq_cookie()
            return APIResponse.success({'content': content, 'configured': bool(content)},
                                       "获取QQ音乐Cookie成功")
        except Exception as e:
            return APIResponse.error(f"获取QQ音乐Cookie失败: {str(e)}", 500)

    @app.route('/api/qq/cookie', methods=['POST'])
    def save_qq_cookie_config():
        try:
            from backend.main import _write_qq_cookie
            data = api_service._safe_get_request_data()
            content = (data.get('content') or '').strip()
            _write_qq_cookie(content)
            return APIResponse.success({'configured': bool(content)},
                                       "QQ音乐Cookie已保存" if content else "QQ音乐Cookie已清空")
        except Exception as e:
            return APIResponse.error(f"保存QQ音乐Cookie失败: {str(e)}", 500)
