"""网易云音乐API服务主程序

提供网易云音乐相关API服务，包括：
- 歌曲信息获取
- 音乐搜索
- 歌单和专辑详情
- 音乐下载
- 健康检查
- 定时歌单同步
"""

import logging
from logging.handlers import RotatingFileHandler
import sys
import time
import traceback
import os
import json
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import quote
import requests
from flask import Flask, request, send_file, render_template, Response, stream_with_context, send_from_directory
from threading import Thread

# 将 backend/ 目录添加到 Python 路径，以支持模块导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from music_api import (
        NeteaseAPI, APIException, QualityLevel,
        url_v1, name_v1, lyric_v1, search_music,
        playlist_detail, album_detail
    )
    from cookie_manager import CookieManager, CookieException
    from music_downloader import MusicDownloader, DownloadException, AudioFormat
    from playlist_sync import PlaylistSyncConfig, PlaylistSyncService, init_sync_service, get_sync_service
    from task_manager import task_manager, TaskManager, TaskStatus, TaskInfo
    from event_bus import (
        event_bus, EventType, Event, fire_event, create_event,
        get_events_catalog, EVENT_DISPLAY_NAMES, EVENT_CATEGORIES
    )
    from push_manager import init_push_routes
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖模块存在且可用")
    sys.exit(1)


@dataclass
class APIConfig:
    """API配置类"""
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False
    downloads_dir: str = 'downloads'
    download_save_local: bool = False
    download_browser: bool = True
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    request_timeout: int = 30
    log_level: str = 'INFO'
    cors_origins: str = '*'
    # 定时同步配置
    enable_sync: bool = False
    playlist_ids: List[str] = None
    sync_quality: str = 'lossless'
    sync_interval: int = 3600
    cron_expression: str = None

    def __post_init__(self):
        if self.playlist_ids is None:
            self.playlist_ids = []


class APIResponse:
    """API响应工具类"""
    
    @staticmethod
    def success(data: Any = None, message: str = 'success', status_code: int = 200) -> Tuple[Dict[str, Any], int]:
        """成功响应"""
        response = {
            'status': status_code,
            'success': True,
            'message': message
        }
        if data is not None:
            response['data'] = data
        return response, status_code
    
    @staticmethod
    def error(message: str, status_code: int = 400, error_code: str = None) -> Tuple[Dict[str, Any], int]:
        """错误响应"""
        response = {
            'status': status_code,
            'success': False,
            'message': message
        }
        if error_code:
            response['error_code'] = error_code
        return response, status_code


class MusicAPIService:
    """音乐API服务类"""
    
    # 暴露 APIResponse 供外部模块使用
    APIResponse = APIResponse
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.cookie_manager = CookieManager()
        self.netease_api = NeteaseAPI()
        self.downloader = MusicDownloader()
        
        # 创建下载目录
        self.downloads_path = Path(config.downloads_dir)
        self.downloads_path.mkdir(exist_ok=True)
        
        # 初始化 sync_service 为 None
        self.sync_service = None
        
        # 从JSON配置文件加载同步配置（优先于环境变量）
        file_config = load_sync_config_from_file()
        if file_config.get('enable_sync', False) and file_config.get('playlist_ids'):
            config.enable_sync = True
            config.playlist_ids = file_config.get('playlist_ids', [])
            config.sync_quality = file_config.get('sync_quality', 'lossless')
            config.sync_interval = file_config.get('sync_interval', 3600)
            config.cron_expression = file_config.get('cron_expression', '')
        
        # 初始化定时同步服务
        self._init_sync_service()
        
        self.logger.info(f"音乐API服务初始化完成，下载目录: {self.downloads_path.absolute()}")
    
    def _init_sync_service(self):
        """初始化定时同步服务"""
        if self.sync_service:
            try:
                self.sync_service.stop()
            except Exception:
                pass
        
        self.sync_service = None
        if self.config.enable_sync and self.config.playlist_ids:
            try:
                sync_config = PlaylistSyncConfig(
                    playlist_ids=self.config.playlist_ids,
                    quality=self.config.sync_quality,
                    sync_interval=self.config.sync_interval,
                    cron_expression=self.config.cron_expression if self.config.cron_expression else None,
                    download_dir=self.config.downloads_dir
                )
                self.sync_service = init_sync_service(sync_config)
                self.logger.info(f"定时同步服务已配置，歌单数量: {len(self.config.playlist_ids)}")
            except Exception as e:
                self.logger.error(f"初始化定时同步服务失败: {e}")
    
    def reload_sync_config(self, new_config: Dict[str, Any]) -> bool:
        """重新加载同步配置（从Web界面调用）"""
        try:
            enable = new_config.get('enable_sync', False)
            playlist_ids = new_config.get('playlist_ids', [])
            if isinstance(playlist_ids, str):
                playlist_ids = [pid.strip() for pid in playlist_ids.split(',') if pid.strip()]
            
            self.config.enable_sync = enable
            self.config.playlist_ids = playlist_ids
            self.config.sync_quality = new_config.get('sync_quality', 'lossless')
            self.config.sync_interval = int(new_config.get('sync_interval', 3600))
            self.config.cron_expression = new_config.get('cron_expression', '')
            
            # 保存到JSON文件
            save_sync_config_to_file({
                'enable_sync': enable,
                'playlist_ids': playlist_ids,
                'sync_quality': self.config.sync_quality,
                'sync_interval': self.config.sync_interval,
                'cron_expression': self.config.cron_expression
            })
            
            # 重新初始化同步服务
            self._init_sync_service()
            
            # 如果新启用了同步，立即启动
            if self.sync_service and enable:
                self.sync_service.start()
            
            self.logger.info(f"同步配置已更新: enable={enable}, playlist_ids={playlist_ids}")
            return True
        except Exception as e:
            self.logger.error(f"重新加载同步配置失败: {e}")
            return False
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('music_api')
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        if not logger.handlers:
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # 文件处理器（单个日志文件最大 2MB，保留 3 个备份）
            try:
                logs_dir = Path('logs')
                logs_dir.mkdir(exist_ok=True)
                log_max_size = 2 * 1024 * 1024  # 2MB
                file_handler = RotatingFileHandler(
                    str(logs_dir / 'music_api.log'),
                    maxBytes=log_max_size,
                    backupCount=3,
                    encoding='utf-8'
                )
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"无法创建日志文件: {e}")
        
        return logger
    
    def _get_cookies(self) -> Dict[str, str]:
        """获取Cookie"""
        try:
            cookie_str = self.cookie_manager.read_cookie()
            return self.cookie_manager.parse_cookie_string(cookie_str)
        except CookieException as e:
            self.logger.warning(f"获取Cookie失败: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Cookie处理异常: {e}")
            return {}
    
    def _extract_music_id(self, id_or_url: str) -> str:
        """提取音乐ID"""
        try:
            # 处理短链接
            if '163cn.tv' in id_or_url:
                import requests
                response = requests.get(id_or_url, allow_redirects=False, timeout=10)
                id_or_url = response.headers.get('Location', id_or_url)
            
            # 处理网易云链接
            if 'music.163.com' in id_or_url:
                index = id_or_url.find('id=') + 3
                if index > 2:
                    return id_or_url[index:].split('&')[0]
            
            # 直接返回ID
            return str(id_or_url).strip()
            
        except Exception as e:
            self.logger.error(f"提取音乐ID失败: {e}")
            return str(id_or_url).strip()
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.2f}{units[unit_index]}"
    
    def _get_quality_display_name(self, quality: str) -> str:
        """获取音质显示名称"""
        quality_names = {
            'standard': "标准音质",
            'exhigh': "极高音质", 
            'lossless': "无损音质",
            'hires': "Hi-Res音质",
            'sky': "沉浸环绕声",
            'jyeffect': "高清环绕声",
            'jymaster': "超清母带",
            'dolby': "杜比全景声"
        }
        return quality_names.get(quality, f"未知音质({quality})")
    
    def _validate_request_params(self, required_params: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], int]]:
        """验证请求参数"""
        for param_name, param_value in required_params.items():
            if not param_value:
                return APIResponse.error(f"参数 '{param_name}' 不能为空", 400)
        return None
    
    def _safe_get_request_data(self) -> Dict[str, Any]:
        """安全获取请求数据"""
        try:
            if request.method == 'GET':
                return dict(request.args)
            else:
                # 优先使用JSON数据，然后是表单数据
                json_data = request.get_json(silent=True) or {}
                form_data = dict(request.form)
                # 合并数据，JSON优先
                return {**form_data, **json_data}
        except Exception as e:
            self.logger.error(f"获取请求数据失败: {e}")
            return {}


# 同步配置文件路径
SYNC_CONFIG_FILE = str(Path('config') / 'sync_config.json')

# 项目配置文件路径
SETTINGS_CONFIG_FILE = str(Path('config') / 'settings.json')


def load_sync_config_from_file() -> Dict[str, Any]:
    """从JSON文件加载同步配置"""
    config_path = Path(SYNC_CONFIG_FILE)
    if config_path.exists():
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_sync_config_to_file(config_data: Dict[str, Any]) -> bool:
    """保存同步配置到JSON文件"""
    try:
        import json
        config_path = Path(SYNC_CONFIG_FILE)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# 操作日志记录器
def _setup_operation_logger():
    """设置操作历史日志（歌单解析、下载记录）"""
    op_logger = logging.getLogger('operation')
    op_logger.setLevel(logging.INFO)
    if not op_logger.handlers:
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        handler = RotatingFileHandler(
            str(logs_dir / 'operation.log'),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        op_logger.addHandler(handler)
    return op_logger

operation_logger = _setup_operation_logger()

# 创建Flask应用和服务实例
config = APIConfig()
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')
app = Flask(__name__, static_folder=os.path.join(FRONTEND_DIR, 'assets'), static_url_path='/assets')
app.config['JSON_AS_ASCII'] = False

api_service = MusicAPIService(config)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """SPA fallback：非 API 路径返回前端 index.html"""
    if path and path.startswith('api/'):
        return  # Let Flask handle API routes normally
    file_path = os.path.join(FRONTEND_DIR, path) if path else os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIR, path) if path else send_from_directory(FRONTEND_DIR, 'index.html')
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.before_request
def before_request():
    """请求前处理"""
    # 记录请求信息
    api_service.logger.info(
        f"{request.method} {request.path} - IP: {request.remote_addr} - "
        f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
    )


@app.after_request
def after_request(response: Response) -> Response:
    """请求后处理 - 设置CORS头"""
    response.headers.add('Access-Control-Allow-Origin', config.cors_origins)
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Max-Age', '3600')
    
    # 记录响应信息
    api_service.logger.info(f"响应状态: {response.status_code}")
    return response


@app.errorhandler(400)
def handle_bad_request(e):
    """处理400错误"""
    return APIResponse.error("请求参数错误", 400)


@app.errorhandler(404)
def handle_not_found(e):
    """处理404错误"""
    return APIResponse.error("请求的资源不存在", 404)


@app.errorhandler(500)
def handle_internal_error(e):
    """处理500错误"""
    api_service.logger.error(f"服务器内部错误: {e}")
    return APIResponse.error("服务器内部错误", 500)


@app.route('/api/api-docs', methods=['GET'])
def api_docs_json():
    """API 文档 JSON 端点"""
    try:
        import json
        config_path = Path('config') / 'api.json'
        if not config_path.exists():
            return APIResponse.error("API 配置文件不存在", 404)
        with open(config_path, 'r', encoding='utf-8') as f:
            api_config = json.load(f)
        return APIResponse.success(api_config, "API文档获取成功")
    except Exception as e:
        api_service.logger.error(f"获取API文档失败: {e}")
        return APIResponse.error(f"获取API文档失败: {str(e)}", 500)


@app.route('/api/logs', methods=['GET'])
def api_logs():
    """日志内容 API——支持指定文件名，返回最近 1000 行（倒序）"""
    try:
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)

        # 获取日志文件列表
        log_files = sorted(
            [f.name for f in logs_dir.glob('*.log')],
            reverse=True
        )

        # 选择文件：参数指定 > 最新的 log
        requested_file = request.args.get('file', '')
        if requested_file:
            log_path = logs_dir / requested_file
            if not log_path.exists():
                return APIResponse.error(f"日志文件 {requested_file} 不存在", 404)
        else:
            if not log_files:
                return APIResponse.success({
                    'files': [],
                    'current_file': '',
                    'lines': [],
                    'total_lines': 0
                }, "暂无日志文件")
            log_path = logs_dir / log_files[0]

        # 读取文件，只取最后 1000 行，倒序输出
        max_lines = int(request.args.get('limit', 1000))
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        recent_lines = all_lines[-max_lines:]
        # 倒序
        recent_lines.reverse()

        return APIResponse.success({
            'files': log_files,
            'current_file': log_path.name,
            'lines': [line.rstrip('\n\r') for line in recent_lines],
            'total_lines': total_lines
        }, "日志获取成功")
    except Exception as e:
        api_service.logger.error(f"获取日志失败: {e}")
        return APIResponse.error(f"获取日志失败: {str(e)}", 500)


@app.route('/api/logs/cleanup', methods=['POST'])
def api_logs_cleanup():
    """清理日志文件——清空所有 .log 文件内容"""
    try:
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)

        cleaned = []
        for log_file in logs_dir.glob('*.log'):
            # 清空文件内容
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('')
            cleaned.append(log_file.name)
            api_service.logger.info(f"已清空日志文件: {log_file.name}")

        if not cleaned:
            return APIResponse.success({'cleaned': []}, "没有可清理的日志文件")

        return APIResponse.success({'cleaned': cleaned}, f"已清空 {len(cleaned)} 个日志文件")
    except Exception as e:
        api_service.logger.error(f"清理日志失败: {e}")
        return APIResponse.error(f"清理日志失败: {str(e)}", 500)


@app.route('/api/tasks', methods=['GET'])
def api_tasks_list():
    """获取任务列表"""
    try:
        task_type = request.args.get('type', '')
        status = request.args.get('status', '')
        limit = int(request.args.get('limit', 50))
        tasks = task_manager.get_tasks(
            task_type=task_type or None,
            status=status or None,
            limit=limit
        )
        return APIResponse.success(
            [task_manager.task_to_dict(t) for t in tasks],
            "任务列表获取成功"
        )
    except Exception as e:
        api_service.logger.error(f"获取任务列表失败: {e}")
        return APIResponse.error(f"获取任务列表失败: {str(e)}", 500)


@app.route('/api/tasks/<task_id>', methods=['GET'])
def api_task_detail(task_id):
    """获取单个任务详情"""
    task = task_manager.get_task(task_id)
    if not task:
        return APIResponse.error("任务不存在", 404)
    return APIResponse.success(task_manager.task_to_dict(task), "任务详情获取成功")


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def api_task_remove(task_id):
    """删除任务记录"""
    if task_manager.remove_task(task_id):
        return APIResponse.success(None, "任务已删除")
    return APIResponse.error("任务不存在", 404)


@app.route('/api/tasks/clear', methods=['POST'])
def api_tasks_clear():
    """清理已完成的任务"""
    count = task_manager.clear_completed()
    return APIResponse.success({'cleared': count}, f"已清理 {count} 个已完成任务")


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查API"""
    try:
        # 检查Cookie状态
        cookie_status = api_service.cookie_manager.is_cookie_valid()
        
        health_info = {
            'service': 'running',
            'timestamp': int(time.time()) if 'time' in sys.modules else None,
            'cookie_status': 'valid' if cookie_status else 'invalid',
            'downloads_dir': str(api_service.downloads_path.absolute()),
            'version': '2.0.0'
        }
        
        return APIResponse.success(health_info, "API服务运行正常")
        
    except Exception as e:
        api_service.logger.error(f"健康检查失败: {e}")
        return APIResponse.error(f"健康检查失败: {str(e)}", 500)


@app.route('/api/song', methods=['GET', 'POST'])
@app.route('/api/Song_V1', methods=['GET', 'POST'])  # 向后兼容
def get_song_info():
    """获取歌曲信息API"""
    try:
        # 获取请求参数
        data = api_service._safe_get_request_data()
        song_ids = data.get('ids') or data.get('id')
        url = data.get('url')
        level = data.get('level', 'lossless')
        info_type = data.get('type', 'url')
        
        # 参数验证
        if not song_ids and not url:
            return APIResponse.error("必须提供 'ids'、'id' 或 'url' 参数")
        
        # 提取音乐ID
        music_id = api_service._extract_music_id(song_ids or url)
        
        # 验证音质参数
        valid_levels = ['standard', 'exhigh', 'lossless', 'hires', 'sky', 'jyeffect', 'jymaster']
        if level not in valid_levels:
            return APIResponse.error(f"无效的音质参数，支持: {', '.join(valid_levels)}")
        
        # 验证类型参数
        valid_types = ['url', 'name', 'lyric', 'json']
        if info_type not in valid_types:
            return APIResponse.error(f"无效的类型参数，支持: {', '.join(valid_types)}")
        
        cookies = api_service._get_cookies()
        
        # 根据类型获取不同信息
        if info_type == 'url':
            result = url_v1(music_id, level, cookies)
            if result and result.get('data') and len(result['data']) > 0:
                song_data = result['data'][0]
                response_data = {
                    'id': song_data.get('id'),
                    'url': song_data.get('url'),
                    'level': song_data.get('level'),
                    'quality_name': api_service._get_quality_display_name(song_data.get('level', level)),
                    'size': song_data.get('size'),
                    'size_formatted': api_service._format_file_size(song_data.get('size', 0)),
                    'type': song_data.get('type'),
                    'bitrate': song_data.get('br')
                }
                return APIResponse.success(response_data, "获取歌曲URL成功")
            else:
                return APIResponse.error("获取音乐URL失败，可能是版权限制或音质不支持", 404)
        
        elif info_type == 'name':
            result = name_v1(music_id)
            fire_event(EventType.SONG_INFO_FETCHED, {
                'music_id': music_id,
                'info_type': 'name',
            }, source='api')
            return APIResponse.success(result, "获取歌曲信息成功")
        
        elif info_type == 'lyric':
            result = lyric_v1(music_id, cookies)
            return APIResponse.success(result, "获取歌词成功")
        
        elif info_type == 'json':
            # 获取完整的歌曲信息（用于前端解析）
            song_info = name_v1(music_id)
            url_info = url_v1(music_id, level, cookies)
            lyric_info = lyric_v1(music_id, cookies)
            
            if not song_info or 'songs' not in song_info or not song_info['songs']:
                return APIResponse.error("未找到歌曲信息", 404)
            
            song_data = song_info['songs'][0]
            
            # 构建前端期望的响应格式
            response_data = {
                'id': music_id,
                'name': song_data.get('name', ''),
                'ar_name': ', '.join(artist['name'] for artist in song_data.get('ar', [])),
                'al_name': song_data.get('al', {}).get('name', ''),
                'pic': song_data.get('al', {}).get('picUrl', ''),
                'level': level,
                'lyric': lyric_info.get('lrc', {}).get('lyric', '') if lyric_info else '',
                'tlyric': lyric_info.get('tlyric', {}).get('lyric', '') if lyric_info else ''
            }
            
            # 添加URL和大小信息
            if url_info and url_info.get('data') and len(url_info['data']) > 0:
                url_data = url_info['data'][0]
                response_data.update({
                    'url': url_data.get('url', ''),
                    'size': api_service._format_file_size(url_data.get('size', 0)),
                    'level': url_data.get('level', level)
                })
            else:
                response_data.update({
                    'url': '',
                    'size': '获取失败'
                })
            
            fire_event(EventType.SONG_INFO_FETCHED, {
                'music_id': music_id,
                'info_type': 'json',
                'song_name': response_data.get('name', ''),
                'artist': response_data.get('ar_name', ''),
            }, source='api')
            return APIResponse.success(response_data, "获取歌曲信息成功")
            
    except APIException as e:
        api_service.logger.error(f"API调用失败: {e}")
        return APIResponse.error(f"API调用失败: {str(e)}", 500)
    except Exception as e:
        api_service.logger.error(f"获取歌曲信息异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"服务器错误: {str(e)}", 500)


@app.route('/api/search', methods=['GET', 'POST'])
@app.route('/api/search', methods=['GET', 'POST'])  # 向后兼容
def search_music_api():
    """搜索音乐API"""
    try:
        # 获取请求参数
        data = api_service._safe_get_request_data()
        keyword = data.get('keyword') or data.get('keywords') or data.get('q')
        limit = int(data.get('limit', 30))
        offset = int(data.get('offset', 0))
        search_type = data.get('type', '1')  # 1-歌曲, 10-专辑, 100-歌手, 1000-歌单
        
        # 参数验证
        validation_error = api_service._validate_request_params({'keyword': keyword})
        if validation_error:
            return validation_error
        
        # 限制搜索数量
        if limit > 100:
            limit = 100
        
        cookies = api_service._get_cookies()
        result = search_music(keyword, cookies, limit)
        
        # search_music返回的是歌曲列表，需要包装成前端期望的格式
        if result:
            for song in result:
                # 添加艺术家字符串（如果需要）
                if 'artists' in song:
                    song['artist_string'] = song['artists']
        
        fire_event(EventType.SEARCH_PERFORMED, {
            'keyword': keyword,
            'result_count': len(result) if result else 0,
        }, source='api')
        return APIResponse.success(result, "搜索完成")
        
    except ValueError as e:
        return APIResponse.error(f"参数格式错误: {str(e)}")
    except Exception as e:
        api_service.logger.error(f"搜索音乐异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"搜索失败: {str(e)}", 500)


@app.route('/api/playlist', methods=['GET', 'POST'])
@app.route('/api/playlist', methods=['GET', 'POST'])  # 向后兼容
def get_playlist():
    """获取歌单详情API"""
    try:
        # 获取请求参数
        data = api_service._safe_get_request_data()
        playlist_id = data.get('id')
        
        # 参数验证
        validation_error = api_service._validate_request_params({'playlist_id': playlist_id})
        if validation_error:
            return validation_error
        
        cookies = api_service._get_cookies()
        result = playlist_detail(playlist_id, cookies)
        
        # 适配前端期望的响应格式
        response_data = {
            'status': 'success',
            'playlist': result
        }
        
        # 记录操作日志
        playlist_name = result.get('name', '未知歌单') if result else '未知歌单'
        operation_logger.info(f"[歌单解析] ID={playlist_id} 名称={playlist_name}")
        fire_event(EventType.PLAYLIST_FETCHED, {
            'playlist_id': playlist_id,
            'playlist_name': playlist_name,
            'track_count': len(result.get('tracks', [])) if result else 0,
        }, source='api')
        return APIResponse.success(response_data, "获取歌单详情成功")
        
    except Exception as e:
        api_service.logger.error(f"获取歌单异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"获取歌单失败: {str(e)}", 500)


@app.route('/api/album', methods=['GET', 'POST'])
@app.route('/api/album', methods=['GET', 'POST'])  # 向后兼容
def get_album():
    """获取专辑详情API"""
    try:
        # 获取请求参数
        data = api_service._safe_get_request_data()
        album_id = data.get('id')
        
        # 参数验证
        validation_error = api_service._validate_request_params({'album_id': album_id})
        if validation_error:
            return validation_error
        
        cookies = api_service._get_cookies()
        result = album_detail(album_id, cookies)
        
        # 适配前端期望的响应格式
        response_data = {
            'status': 200,
            'album': result
        }
        
        fire_event(EventType.ALBUM_FETCHED, {
            'album_id': album_id,
            'album_name': result.get('name', '') if result else '',
        }, source='api')
        return APIResponse.success(response_data, "获取专辑详情成功")
        
    except Exception as e:
        api_service.logger.error(f"获取专辑异常: {e}\n{traceback.format_exc()}")
        fire_event(EventType.API_ERROR, {
            'endpoint': '/album',
            'error': str(e),
        }, source='api')
        return APIResponse.error(f"获取专辑失败: {str(e)}", 500)


@app.route('/api/download', methods=['GET', 'POST'])
@app.route('/api/download', methods=['GET', 'POST'])  # 向后兼容
def download_music_api():
    """下载音乐API"""
    try:
        # 获取请求参数
        data = api_service._safe_get_request_data()
        music_id = data.get('id')
        quality = data.get('quality', 'lossless')
        return_format = data.get('format', 'file')  # file 或 json

        # 读取下载配置
        save_local = config.download_save_local
        browser_download = config.download_browser
        download_dir = Path(config.downloads_dir)
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # 参数验证
        validation_error = api_service._validate_request_params({'music_id': music_id})
        if validation_error:
            return validation_error
        
        # 验证音质参数
        valid_qualities = ['standard', 'exhigh', 'lossless', 'hires', 'sky', 'jyeffect', 'jymaster']
        if quality not in valid_qualities:
            return APIResponse.error(f"无效的音质参数，支持: {', '.join(valid_qualities)}")
        
        # 验证返回格式
        if return_format not in ['file', 'json']:
            return APIResponse.error("返回格式只支持 'file' 或 'json'")
        
        music_id = api_service._extract_music_id(music_id)
        cookies = api_service._get_cookies()
        
        # 创建下载任务
        task = task_manager.create_task('download', f'下载中...', music_id=music_id, quality=quality)

        # 触发下载开始事件
        fire_event(EventType.DOWNLOAD_STARTED, {
            'music_id': music_id,
            'quality': quality,
            'task_id': task.task_id,
        }, source='api', async_mode=True)
        
        try:
            # 获取音乐基本信息
            task_manager.update_task(task.task_id, status=TaskStatus.RUNNING, message='正在获取歌曲信息...', progress=10)
            song_info = name_v1(music_id)
            if not song_info or 'songs' not in song_info or not song_info['songs']:
                task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='未找到音乐信息', error='歌曲不存在')
                return APIResponse.error("未找到音乐信息", 404)
            
            # 获取音乐下载链接（支持音质降级）
            task_manager.update_task(task.task_id, message='正在获取下载链接...', progress=30)
            quality_order = ['jymaster', 'sky', 'jyeffect', 'hires', 'lossless', 'exhigh', 'standard']
            actual_quality = quality
            url_info = None

            # 从请求的音质开始，逐级降级尝试
            try:
                start_idx = quality_order.index(quality) if quality in quality_order else len(quality_order) - 1
            except ValueError:
                start_idx = len(quality_order) - 1

            for q in quality_order[start_idx:]:
                url_info = url_v1(music_id, q, cookies)
                if url_info and url_info.get('data') and len(url_info['data']) > 0 and url_info['data'][0].get('url'):
                    actual_quality = q
                    if q != quality:
                        task_manager.update_task(task.task_id, message=f'请求的音质不可用，已降级为 {q}', progress=35)
                        api_service.logger.info(f"音质降级: {quality} -> {q} for {music_id}")
                        fire_event(EventType.DOWNLOAD_QUALITY_DOWNGRADED, {
                            'music_id': music_id,
                            'original_quality': quality,
                            'actual_quality': q,
                        }, source='api', async_mode=True)
                    break
                else:
                    api_service.logger.info(f"音质 {q} 不可用 for {music_id}，尝试下一级")
                    url_info = None

            if not url_info:
                task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='所有音质均不可用', error='版权限制或音质不支持')
                return APIResponse.error("无法获取音乐下载链接，可能是版权限制或音质不支持", 404)
            
            # 构建音乐信息
            song_data = song_info['songs'][0]
            url_data = url_info['data'][0]
            song_name = song_data['name']
            artist_name = ', '.join(artist['name'] for artist in song_data['ar'])
            
            task_manager.update_task(task.task_id, name=song_name, extra={
                'artist': artist_name,
                'album': song_data['al']['name'],
                'quality': actual_quality
            })
            
            music_info = {
                'id': music_id,
                'name': song_name,
                'artist_string': artist_name,
                'album': song_data['al']['name'],
                'pic_url': song_data['al']['picUrl'],
                'file_type': url_data['type'],
                'file_size': url_data['size'],
                'duration': song_data.get('dt', 0),
                'download_url': url_data['url']
            }
            
            # 生成安全文件名
            safe_name = f"{music_info['name']} [{actual_quality}]"
            safe_name = ''.join(c for c in safe_name if c not in r'<>:"/\|?*')
            filename = f"{safe_name}.{music_info['file_type']}"
            download_url = music_info['download_url']

            # 模式 3: 仅保存到本地，后台下载 + JSON 通知
            if save_local and not browser_download:
                file_path = download_dir / filename
                if file_path.exists():
                    api_service.logger.info(f"文件已存在: {filename}")
                    operation_logger.info(f"[音乐下载] ID={music_id} 歌名={song_name} 歌手={artist_name} 音质={actual_quality} (文件已存在)")
                    task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED, message='文件已存在', progress=100)
                    fire_event(EventType.DOWNLOAD_COMPLETED, {
                        'music_id': music_id,
                        'song_name': song_name,
                        'artist': artist_name,
                        'quality': actual_quality,
                        'file_size': api_service._format_file_size(url_data.get('size', 0)),
                        'mode': 'local_only',
                    }, source='api', async_mode=True)
                else:
                    task_manager.update_task(task.task_id, message='正在后台下载...', progress=50)
                    # 后台线程下载
                    def _bg_download():
                        try:
                            r = requests.get(download_url, stream=True, timeout=60)
                            r.raise_for_status()
                            with open(file_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED, message='下载完成', progress=100)
                            operation_logger.info(f"[音乐下载] ID={music_id} 歌名={song_name} 歌手={artist_name} 音质={actual_quality} (仅本地)")
                            fire_event(EventType.DOWNLOAD_COMPLETED, {
                                'music_id': music_id,
                                'song_name': song_name,
                                'artist': artist_name,
                                'quality': actual_quality,
                                'file_size': api_service._format_file_size(url_data.get('size', 0)),
                                'mode': 'local_only',
                            }, source='api', async_mode=True)
                        except Exception as e:
                            task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='下载失败', error=str(e))
                            fire_event(EventType.DOWNLOAD_FAILED, {
                                'music_id': music_id,
                                'song_name': song_name,
                                'artist': artist_name,
                                'error': str(e),
                            }, source='api', async_mode=True)
                    Thread(target=_bg_download, daemon=True).start()
                response_data = {
                    'music_id': music_id,
                    'name': music_info['name'],
                    'artist': music_info['artist_string'],
                    'album': music_info['album'],
                    'quality': quality,
                    'file_type': music_info['file_type'],
                    'file_size': music_info['file_size'],
                    'filename': filename,
                    'mode': 'local_only'
                }
                return APIResponse.success(response_data, "已开始后台保存到本地")

            # 模式 1 & 2: 流式代理（浏览器即时下载 + 可选本地保存）
            # 打开本地文件句柄（save_local 模式）
            if save_local:
                file_path = download_dir / filename
                local_f = open(file_path, 'wb')
            else:
                local_f = None

            def stream_proxy():
                try:
                    r = requests.get(download_url, stream=True, timeout=60)
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=65536):
                        if local_f:
                            local_f.write(chunk)
                        yield chunk
                    task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED, message='下载完成', progress=100)
                    tag = " (保存+浏览器)" if save_local else " (仅浏览器)"
                    operation_logger.info(f"[音乐下载] ID={music_id} 歌名={song_name} 歌手={artist_name} 音质={actual_quality}{tag}")
                    fire_event(EventType.DOWNLOAD_COMPLETED, {
                        'music_id': music_id,
                        'song_name': song_name,
                        'artist': artist_name,
                        'quality': actual_quality,
                        'file_size': api_service._format_file_size(url_data.get('size', 0)),
                        'mode': 'browser' if not save_local else 'both',
                    }, source='api', async_mode=True)
                except Exception as e:
                    api_service.logger.error(f"流式下载异常: {e}")
                    task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='下载失败', error=str(e))
                    fire_event(EventType.DOWNLOAD_FAILED, {
                        'music_id': music_id,
                        'song_name': song_name,
                        'artist': artist_name,
                        'error': str(e),
                    }, source='api', async_mode=True)
                finally:
                    if local_f:
                        local_f.close()

            resp = Response(stream_with_context(stream_proxy()), mimetype=f"audio/{music_info['file_type']}")
            resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
            resp.headers['X-Download-Filename'] = quote(filename, safe='')
            return resp

        except Exception as inner_e:
            task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='下载过程出错', error=str(inner_e))
            raise
            
    except Exception as e:
        api_service.logger.error(f"下载音乐异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"下载异常: {str(e)}", 500)


@app.route('/api/info', methods=['GET'])
def api_info():
    """API信息接口"""
    try:
        info = {
            'name': '网易云音乐API服务',
            'version': '2.0.0',
            'description': '提供网易云音乐相关API服务',
            'endpoints': {
                '/health': 'GET - 健康检查',
                '/song': 'GET/POST - 获取歌曲信息',
                '/search': 'GET/POST - 搜索音乐',
                '/playlist': 'GET/POST - 获取歌单详情',
                '/album': 'GET/POST - 获取专辑详情',
                '/download': 'GET/POST - 下载音乐',
                '/sync/status': 'GET - 获取同步状态',
                '/sync/config': 'GET/POST - 获取/保存同步配置',
                '/sync/now': 'POST - 立即执行同步',
                '/api/info': 'GET - API信息',
                '/api-docs': 'GET - API文档页面',
                '/api/api-docs': 'GET - API文档JSON'
            },
            'supported_qualities': [
                'standard', 'exhigh', 'lossless', 
                'hires', 'sky', 'jyeffect', 'jymaster'
            ],
            'config': {
                'downloads_dir': str(api_service.downloads_path.absolute()),
                'max_file_size': f"{config.max_file_size // (1024*1024)}MB",
                'request_timeout': f"{config.request_timeout}s",
                'sync_enabled': config.enable_sync,
                'sync_playlist_count': len(config.playlist_ids) if config.playlist_ids else 0
            }
        }
        
        return APIResponse.success(info, "API信息获取成功")
        
    except Exception as e:
        api_service.logger.error(f"获取API信息异常: {e}")
        return APIResponse.error(f"获取API信息失败: {str(e)}", 500)


@app.route('/api/sync/config', methods=['GET'])
def get_sync_config():
    """获取同步配置"""
    try:
        file_config = load_sync_config_from_file()
        if file_config:
            config_data = file_config
        else:
            config_data = {
                'enable_sync': config.enable_sync,
                'playlist_ids': config.playlist_ids,
                'sync_quality': config.sync_quality,
                'sync_interval': config.sync_interval,
                'cron_expression': config.cron_expression or ''
            }
        return APIResponse.success(config_data, "获取同步配置成功")
    except Exception as e:
        api_service.logger.error(f"获取同步配置异常: {e}")
        return APIResponse.error(f"获取同步配置失败: {str(e)}", 500)


@app.route('/api/sync/config', methods=['POST'])
def save_sync_config():
    """保存同步配置（从Web界面）"""
    try:
        data = api_service._safe_get_request_data()
        
        if api_service.reload_sync_config(data):
            fire_event(EventType.SYNC_CONFIG_UPDATED, {
                'enable_sync': data.get('enable_sync', False),
                'playlist_count': len(data.get('playlist_ids', [])),
            }, source='api')
            return APIResponse.success(
                {'message': '配置已保存，同步服务已更新'},
                "配置保存成功"
            )
        else:
            return APIResponse.error("配置保存失败", 500)
    except Exception as e:
        api_service.logger.error(f"保存同步配置异常: {e}")
        return APIResponse.error(f"保存同步配置失败: {str(e)}", 500)


@app.route('/api/sync/status', methods=['GET'])
def get_sync_status():
    """获取定时同步状态"""
    try:
        sync_service = get_sync_service()
        
        if not sync_service:
            return APIResponse.error("定时同步服务未启用", 400)
        
        status = sync_service.get_sync_status()
        return APIResponse.success(status, "获取同步状态成功")
        
    except Exception as e:
        api_service.logger.error(f"获取同步状态异常: {e}")
        return APIResponse.error(f"获取同步状态失败: {str(e)}", 500)


@app.route('/api/sync/now', methods=['POST'])
def trigger_sync_now():
    """立即执行歌单同步"""
    try:
        sync_service = get_sync_service()
        
        if not sync_service:
            return APIResponse.error("定时同步服务未启用", 400)
        
        # 在后台线程执行同步
        thread = Thread(target=sync_service.sync_all_playlists, daemon=True)
        thread.start()
        
        return APIResponse.success(
            {'message': '同步任务已在后台启动'},
            "同步任务已启动"
        )
        
    except Exception as e:
        api_service.logger.error(f"触发同步异常: {e}")
        return APIResponse.error(f"触发同步失败: {str(e)}", 500)


@app.route('/api/cookie', methods=['GET'])
def get_cookie_config():
    """获取Cookie配置信息"""
    try:
        cookie_info = api_service.cookie_manager.get_cookie_info()
        cookie_content = api_service.cookie_manager.read_cookie()
        return APIResponse.success({
            'info': cookie_info,
            'content': cookie_content,
            'file_path': str(api_service.cookie_manager.cookie_file)
        }, "获取Cookie配置成功")
    except Exception as e:
        api_service.logger.error(f"获取Cookie配置异常: {e}")
        return APIResponse.error(f"获取Cookie配置失败: {str(e)}", 500)


@app.route('/api/cookie', methods=['POST'])
def save_cookie_config():
    """保存Cookie配置"""
    try:
        data = api_service._safe_get_request_data()
        cookie_content = (data.get('cookie') or data.get('content') or '').strip()

        if not cookie_content:
            # 允许清空
            api_service.cookie_manager.clear_cookie()
            return APIResponse.success(None, "Cookie已清空")

        # 验证格式
        if not api_service.cookie_manager.validate_cookie_format(cookie_content):
            return APIResponse.error("Cookie格式无效，请检查内容", 400)

        # 写入文件
        api_service.cookie_manager.write_cookie(cookie_content)

        fire_event(EventType.COOKIE_UPDATED, {
            'has_content': bool(cookie_content),
        }, source='api')

        # 验证保存结果
        info = api_service.cookie_manager.get_cookie_info()
        return APIResponse.success({
            'info': info,
            'saved': info['is_valid']
        }, "Cookie配置保存成功" if info['is_valid'] else "Cookie已保存但可能不完整")
    except Exception as e:
        api_service.logger.error(f"保存Cookie配置异常: {e}")
        return APIResponse.error(f"保存Cookie配置失败: {str(e)}", 500)


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取下载等通用配置"""
    try:
        return APIResponse.success({
            'downloads_dir': config.downloads_dir,
            'download_save_local': config.download_save_local,
            'download_browser': config.download_browser,
        }, "获取配置成功")
    except Exception as e:
        return APIResponse.error(f"获取配置失败: {str(e)}", 500)


@app.route('/api/settings', methods=['POST'])
def save_settings():
    """保存下载等通用配置到 settings.json"""
    try:
        data = api_service._safe_get_request_data()

        if 'downloads_dir' in data:
            config.downloads_dir = data['downloads_dir']
        if 'download_save_local' in data:
            config.download_save_local = str(data['download_save_local']).lower() in ('true', '1', 'yes')
        if 'download_browser' in data:
            config.download_browser = str(data['download_browser']).lower() in ('true', '1', 'yes')

        # 保存到 settings.json
        settings_path = Path(SETTINGS_CONFIG_FILE)
        current = {}
        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                current = json.load(f)
        current['downloads_dir'] = config.downloads_dir
        current['download_save_local'] = config.download_save_local
        current['download_browser'] = config.download_browser
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

        fire_event(EventType.SETTINGS_UPDATED, {
            'downloads_dir': config.downloads_dir,
            'download_save_local': config.download_save_local,
            'download_browser': config.download_browser,
        }, source='api')

        return APIResponse.success({
            'downloads_dir': config.downloads_dir,
            'download_save_local': config.download_save_local,
            'download_browser': config.download_browser,
        }, "配置保存成功")
    except Exception as e:
        api_service.logger.error(f"保存配置异常: {e}")
        return APIResponse.error(f"保存配置失败: {str(e)}", 500)


def start_api_server():
    """启动API服务器"""
    try:
        print("\n" + "="*60)
        print("🚀 网易云音乐API服务启动中...")
        print("="*60)
        print(f"📡 服务地址: http://{config.host}:{config.port}")
        print(f"📁 下载目录: {api_service.downloads_path.absolute()}")
        print(f"📋 日志级别: {config.log_level}")
        
        # 显示定时同步配置
        if config.enable_sync and config.playlist_ids:
            print("\n⏰ 定时同步服务:")
            print(f"  ├─ 启用状态: ✓ 已启用")
            print(f"  ├─ 歌单数量: {len(config.playlist_ids)}")
            print(f"  ├─ 同步音质: {config.sync_quality}")
            if config.cron_expression:
                print(f"  └─ Cron表达式: {config.cron_expression}")
            else:
                print(f"  └─ 同步间隔: {config.sync_interval}秒")
        else:
            print("\n⏰ 定时同步服务: ✗ 未启用")
        
        print("\n📚 API端点:")
        print(f"  ├─ GET  /health        - 健康检查")
        print(f"  ├─ POST /song          - 获取歌曲信息")
        print(f"  ├─ POST /search        - 搜索音乐")
        print(f"  ├─ POST /playlist      - 获取歌单详情")
        print(f"  ├─ POST /album         - 获取专辑详情")
        print(f"  ├─ POST /download      - 下载音乐")
        print(f"  ├─ GET  /sync/status   - 同步状态")
        print(f"  ├─ GET  /sync/config   - 同步配置")
        print(f"  ├─ POST /sync/config   - 保存配置")
        print(f"  ├─ POST /sync/now      - 立即同步")
        print(f"  ├─ GET  /api/info      - API信息")
        print(f"  ├─ GET  /api-docs      - API文档页面")
        print(f"  ├─ GET  /api/api-docs  - API文档JSON")
        print(f"  ├─ GET  /api/cookie    - Cookie配置")
        print(f"  ├─ POST /api/cookie    - 保存Cookie")
        print(f"  ├─ GET  /logs          - 日志查看页面")
        print(f"  └─ GET  /api/logs      - 日志内容API")
        print("\n🎵 支持的音质:")
        print(f"  standard, exhigh, lossless, hires, sky, jyeffect, jymaster")
        print("="*60)
        print(f"⏰ 启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("🌟 服务已就绪，等待请求...\n")

        # 初始化推送管理和事件路由
        init_push_routes(app, api_service)

        # 触发服务启动事件
        fire_event(EventType.SERVER_STARTED, {
            'host': config.host,
            'port': config.port,
            'version': '2.0.0',
        }, source='server', async_mode=True)
        
        # 启动定时同步服务
        if api_service.sync_service:
            try:
                api_service.sync_service.start()
            except Exception as e:
                api_service.logger.error(f"启动定时同步服务失败: {e}")
        
        # 启动Flask应用
        app.run(
            host=config.host,
            port=config.port,
            debug=config.debug,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
        # 停止定时同步服务
        if api_service.sync_service:
            api_service.sync_service.stop()
    except Exception as e:
        api_service.logger.error(f"启动服务失败: {e}")
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


# ===== 文件管理 =====

@app.route('/api/files/list', methods=['GET'])
def api_files_list():
    """获取下载目录文件列表"""
    try:
        downloads_dir = Path(config.downloads_dir)
        downloads_dir.mkdir(exist_ok=True)
        files = []
        for f in sorted(downloads_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file():
                stat = f.stat()
                files.append({
                    'name': f.name,
                    'size': stat.st_size,
                    'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                })
        return APIResponse.success({'files': files, 'dir': str(downloads_dir.absolute())}, "文件列表获取成功")
    except Exception as e:
        return APIResponse.error(f"获取文件列表失败: {str(e)}", 500)


@app.route('/api/files/delete', methods=['POST'])
def api_files_delete():
    """删除文件"""
    try:
        data = api_service._safe_get_request_data()
        filename = data.get('filename', '').strip()
        if not filename:
            return APIResponse.error("文件名不能为空", 400)
        file_path = Path(config.downloads_dir) / filename
        # 安全检查：确保文件在 downloads 目录内
        if not file_path.resolve().is_relative_to(Path(config.downloads_dir).resolve()):
            return APIResponse.error("非法文件路径", 403)
        if not file_path.exists():
            return APIResponse.error("文件不存在", 404)
        file_path.unlink()
        api_service.logger.info(f"文件已删除: {filename}")
        return APIResponse.success({'filename': filename}, "文件已删除")
    except Exception as e:
        return APIResponse.error(f"删除文件失败: {str(e)}", 500)


@app.route('/api/files/stream/<path:filename>', methods=['GET'])
def api_files_stream(filename):
    """流式传输文件（用于音频播放和下载）"""
    try:
        file_path = Path(config.downloads_dir) / filename
        if not file_path.resolve().is_relative_to(Path(config.downloads_dir).resolve()):
            return APIResponse.error("非法文件路径", 403)
        if not file_path.exists():
            return APIResponse.error("文件不存在", 404)

        download = request.args.get('download', '0') == '1'
        mimetype = 'application/octet-stream'
        ext = file_path.suffix.lower()
        mime_map = {'.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.m4a': 'audio/mp4',
                     '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.wma': 'audio/x-ms-wma'}
        mimetype = mime_map.get(ext, mimetype)

        response = send_file(str(file_path), mimetype=mimetype, as_attachment=download)
        if not download:
            response.headers['Accept-Ranges'] = 'bytes'
        return response
    except Exception as e:
        return APIResponse.error(f"文件传输失败: {str(e)}", 500)


@app.route('/api/files/read/<path:filename>', methods=['GET'])
def api_files_read(filename):
    """读取文本文件内容"""
    try:
        file_path = Path(config.downloads_dir) / filename
        if not file_path.resolve().is_relative_to(Path(config.downloads_dir).resolve()):
            return APIResponse.error("非法文件路径", 403)
        if not file_path.exists():
            return APIResponse.error("文件不存在", 404)
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return APIResponse.success({'filename': filename, 'content': content}, "文件读取成功")
    except Exception as e:
        return APIResponse.error(f"读取文件失败: {str(e)}", 500)


@app.route('/api/files/save', methods=['POST'])
def api_files_save():
    """保存文本文件内容"""
    try:
        data = api_service._safe_get_request_data()
        filename = data.get('filename', '').strip()
        content = data.get('content', '')
        if not filename:
            return APIResponse.error("文件名不能为空", 400)
        file_path = Path(config.downloads_dir) / filename
        if not file_path.resolve().is_relative_to(Path(config.downloads_dir).resolve()):
            return APIResponse.error("非法文件路径", 403)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        api_service.logger.info(f"文件已保存: {filename}")
        return APIResponse.success({'filename': filename}, "文件保存成功")
    except Exception as e:
        return APIResponse.error(f"保存文件失败: {str(e)}", 500)


if __name__ == '__main__':
    # 加载.env文件
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # .env文件不是必须的
    
    # 加载 config/settings.json（优先级最高）
    def load_settings_json() -> Dict[str, Any]:
        """从 config/settings.json 加载项目配置"""
        settings_path = Path('config') / 'settings.json'
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    settings = load_settings_json()
    
    # 从环境变量读取基础配置（settings.json > .env > 默认值）
    def parse_env_list(env_var: str, default: str = "") -> List[str]:
        """解析环境变量中的列表（逗号分隔）"""
        value = os.getenv(env_var, default)
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]
    
    # 先尝试从sync_config.json加载同步配置
    file_config = load_sync_config_from_file()
    
    # 更新全局config对象（settings.json > 环境变量 > 默认值）
    config.host = settings.get('host', os.getenv('HOST', '0.0.0.0'))
    config.port = int(settings.get('port', os.getenv('PORT', '5000')))
    config.debug = settings.get('debug', os.getenv('DEBUG', 'false').lower() == 'true')
    config.downloads_dir = settings.get('downloads_dir', os.getenv('DOWNLOADS_DIR', 'downloads'))
    config.download_save_local = settings.get('download_save_local', os.getenv('DOWNLOAD_SAVE_LOCAL', 'false').lower() in ('true', '1', 'yes'))
    config.download_browser = settings.get('download_browser', os.getenv('DOWNLOAD_BROWSER', 'true').lower() in ('true', '1', 'yes'))
    config.log_level = settings.get('log_level', os.getenv('LOG_LEVEL', 'INFO'))
    config.max_file_size = int(settings.get('max_file_size', os.getenv('MAX_FILE_SIZE', str(config.max_file_size))))
    config.request_timeout = int(settings.get('request_timeout', os.getenv('REQUEST_TIMEOUT', str(config.request_timeout))))
    # 定时同步配置：优先使用JSON文件配置，其次环境变量
    config.enable_sync = file_config.get('enable_sync', settings.get('enable_sync', os.getenv('ENABLE_SYNC', 'false').lower() == 'true'))
    config.playlist_ids = file_config.get('playlist_ids', settings.get('playlist_ids', parse_env_list('PLAYLIST_IDS')))
    config.sync_quality = file_config.get('sync_quality', settings.get('sync_quality', os.getenv('SYNC_QUALITY', os.getenv('LEVEL', 'lossless'))))
    config.sync_interval = int(file_config.get('sync_interval', settings.get('sync_interval', os.getenv('SYNC_INTERVAL', '3600'))))
    config.cron_expression = file_config.get('cron_expression', settings.get('cron_expression', os.getenv('CRON_EXPRESSION', ''))) or None
    
    start_api_server()

