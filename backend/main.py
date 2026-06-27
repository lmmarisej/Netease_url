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
import threading
import traceback
import os
import json
import sqlite3
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import quote
import requests
from flask import Flask, request, send_file, render_template, Response, stream_with_context, send_from_directory
from threading import Thread

# 将 backend/ 目录和项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from music_api import (
        NeteaseAPI, APIException, QualityLevel,
        url_v1, name_v1, lyric_v1, search_music,
        playlist_detail, album_detail
    )
    from qq_music_api import (
        QQMusicAPI, QQAPIException,
        qq_search_music, qq_song_detail, qq_song_url, qq_lyric,
        map_quality_to_qq,
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
    from lyrics_db import LyricsDB, save_lyric_from_music_info, get_lyrics_db_path
    from auth import (
        verify_credentials, generate_token, verify_token,
        get_current_user, set_current_user, login_required,
        get_user_config_path, get_user_downloads_dir, get_user_config_dir,
        register_user
    )
    from recommendation_engine import (
        get_recommendation_engine,
        FEATURE_KEYS, SLOT_HOUR_RANGES,
    )
    from playback_api import (
        PlayLogRequest, PlaybackLog, SessionLocal,
        _load_netease_cookies as _pb_load_cookies,
        _get_liked_ids,
        _build_recommend_tracks, _get_local_features,
        _get_local_top_tracks, _async_download_and_score, compute_preference_score,
        _sort_tracks_by_preference, _async_fetch_netease_playlist,
    )
    from music_api import playlist_detail as netease_playlist_detail, APIException as NeteaseAPIError
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖模块存在且可用")
    sys.exit(1)


# ────────────────────────── 推荐引擎实例（v3 复用） ──────────────────────────

_recommendation_engine = None


def _get_recommendation_engine():
    global _recommendation_engine
    if _recommendation_engine is None:
        _recommendation_engine = get_recommendation_engine()
    return _recommendation_engine


_NETEASE_HOT_CHART_ID = 3778678

# ── 喜欢ID缓存 ──
_liked_ids_cache = None
_liked_ids_cookie_hash = None
# ── 喜欢歌曲完整信息缓存（用于搜索） ──
_liked_songs_cache = None
_liked_songs_cookie_hash = None


from api_core import APIConfig, APIResponse, set_project_root

# 设置项目根目录
set_project_root(_PROJECT_ROOT)


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
        
        # 创建下载目录（基于项目根目录）
        self.downloads_path = _PROJECT_ROOT / 'downloads'
        config.downloads_dir = str(self.downloads_path)
        self.downloads_path.mkdir(parents=True, exist_ok=True)
        
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
                    download_dir=str(_get_user_downloads_path()),
                    cookie_file=_get_user_cookie_path() if get_current_user() else None,
                    sync_full_delete=getattr(self.config, 'sync_full_delete', False),
                    sync_dedup_files=getattr(self.config, 'sync_dedup_files', False)
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
            self.config.sync_full_delete = new_config.get('sync_full_delete', False)
            self.config.sync_dedup_files = new_config.get('sync_dedup_files', False)
            
            # 保存到JSON文件
            save_sync_config_to_file({
                'enable_sync': enable,
                'playlist_ids': playlist_ids,
                'sync_quality': self.config.sync_quality,
                'sync_interval': self.config.sync_interval,
                'cron_expression': self.config.cron_expression,
                'sync_full_delete': self.config.sync_full_delete,
                'sync_dedup_files': self.config.sync_dedup_files
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
                logs_dir = _PROJECT_ROOT / 'logs'
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
        """获取Cookie（自动切换到用户专属文件）"""
        try:
            username = get_current_user()
            if username:
                user_path = _get_user_cookie_path()
                if user_path and Path(user_path).parent.exists():  # 仅在用户目录已存在时切换
                    self.cookie_manager.set_cookie_file(user_path)
            cookie_str = self.cookie_manager.read_cookie()
            return self.cookie_manager.parse_cookie_string(cookie_str)
        except CookieException as e:
            self.logger.warning(f"获取Cookie失败: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Cookie处理异常: {e}")
            return {}
    
    def _extract_music_id(self, id_or_url) -> str:
        """提取音乐ID，兼容 int 和 str 类型"""
        try:
            # 统一转为字符串
            id_or_url = str(id_or_url)
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


# 同步配置文件路径（支持用户维度）
def _get_user_sync_config_path() -> str:
    username = get_current_user()
    if username:
        return str(get_user_config_path(username, 'sync_config.json'))
    return str(_PROJECT_ROOT / 'config' / 'sync_config.json')


def _get_user_settings_path() -> str:
    username = get_current_user()
    if username:
        return str(get_user_config_path(username, 'settings.json'))
    return str(_PROJECT_ROOT / 'config' / 'settings.json')


def _get_user_push_config_path() -> str:
    username = get_current_user()
    if username:
        return str(get_user_config_path(username, 'push_config.json'))
    return str(_PROJECT_ROOT / 'config' / 'push_config.json')


def _get_user_cookie_path() -> str:
    username = get_current_user()
    if username:
        return str(get_user_config_path(username, 'cookies.json'))
    # 回退到共享配置
    return str(Path(os.path.dirname(os.path.abspath(__file__))).parent / 'config' / 'cookies.json')


def _get_user_qq_cookie_path() -> Path:
    """获取QQ音乐Cookie存储路径（按用户隔离）"""
    username = get_current_user()
    if username:
        return get_user_config_path(username, 'qq_cookie.json')
    return Path(os.path.dirname(os.path.abspath(__file__))).parent / 'config' / 'qq_cookie.json'


def _read_qq_cookie() -> str:
    """读取当前用户配置的QQ音乐Cookie字符串，未配置返回空串"""
    try:
        path = _get_user_qq_cookie_path()
        if path.exists():
            with open(path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            return (data.get('content') or '').strip()
    except Exception as e:
        api_service.logger.warning(f"读取QQ音乐Cookie失败: {e}")
    return ''


def _write_qq_cookie(content: str) -> None:
    """写入当前用户的QQ音乐Cookie字符串"""
    path = _get_user_qq_cookie_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'content': (content or '').strip()}, f, ensure_ascii=False, indent=2)


def _get_user_downloads_path() -> Path:
    """获取用户专属下载目录路径"""
    username = get_current_user()
    if username:
        p = get_user_downloads_dir(username)
        p.mkdir(parents=True, exist_ok=True)
        return p
    # 回退时使用项目根目录 + downloads
    p = _PROJECT_ROOT / 'downloads'
    p.mkdir(parents=True, exist_ok=True)
    return p


def _extract_uid_from_cookies(cookies: Dict[str, str]) -> int:
    """通过网易云账户 API 获取用户 UID"""
    try:
        from music_api import user_account
        result = user_account(cookies)
        uid = result.get('account', {}).get('id', 0)
        if uid:
            return uid
    except Exception:
        pass
    return 0


SYNC_CONFIG_FILE = str(_PROJECT_ROOT / 'config' / 'sync_config.json')
SETTINGS_CONFIG_FILE = str(_PROJECT_ROOT / 'config' / 'settings.json')


def load_sync_config_from_file() -> Dict[str, Any]:
    """从JSON文件加载同步配置（优先用户专属）"""
    # 优先加载用户专属配置
    username = get_current_user()
    if username:
        user_path = Path(_get_user_sync_config_path())
        if user_path.exists():
            try:
                import json
                with open(user_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
    # 回退到共享配置
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
    """保存同步配置到JSON文件（用户专属）"""
    try:
        import json
        username = get_current_user()
        if username:
            config_path = Path(_get_user_sync_config_path())
        else:
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
        logs_dir = _PROJECT_ROOT / 'logs'
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
app.json.ensure_ascii = False

# 初始化核心数据库表（music_tracks / track_audio_features / track_tags / user_track_behaviors）
from music_processor.database import init_database
init_database(_PROJECT_ROOT / 'config' / 'music_vault.db')

api_service = MusicAPIService(config)

# ── 注册所有路由模块（从 routes_flask/ 懒加载） ──
from routes_flask import register_all_routes
register_all_routes(app, api_service, config, operation_logger, _PROJECT_ROOT)

# ── 注册集合 & 歌单解析路由 ──
from collection_api import register_collection_routes
register_collection_routes(app)

# ── 全局引用（供 route 模块懒导入） ──
_NETEASE_HOT_CHART_ID = 3778678
_liked_ids_cache = None
_liked_ids_cookie_hash = None
_liked_songs_cache = None
_liked_songs_cookie_hash = None
_liked_pid_cache = None


def _get_liked_pid() -> Optional[int]:
    """获取喜欢歌单 ID（带缓存）"""
    global _liked_pid_cache
    if _liked_pid_cache:
        return _liked_pid_cache
    cookies = _pb_load_cookies()
    if not cookies:
        return None
    try:
        from music_api import user_account, user_playlist
        account = user_account(cookies)
        uid = account.get('account', {}).get('id', 0)
        if not uid:
            return None
        playlists = user_playlist(uid, cookies, limit=50)
        for p in playlists.get('playlist', []):
            if p.get('specialType') == 5:
                _liked_pid_cache = p['id']
                return _liked_pid_cache
    except Exception:
        pass
    return None


def _fetch_liked_ids_direct() -> List[int]:
    """直接拉取喜欢歌单的 trackIds（不依赖缓存），用于重建任务冷启动"""
    try:
        liked_pid = _get_liked_pid()
        if not liked_pid:
            return []
        cookies = _pb_load_cookies()
        if not cookies:
            return []
        import requests as _r
        url = f"https://music.163.com/api/v6/playlist/detail?id={liked_pid}"
        hdrs = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://music.163.com/',
        }
        resp = _r.get(url, headers=hdrs, cookies=cookies, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if body.get('code') != 200:
            return []
        return [t['id'] for t in body.get('playlist', {}).get('trackIds', [])]
    except Exception as e:
        api_service.logger.error(f"_fetch_liked_ids_direct 失败: {e}")
        return []


def start_api_server():
    """启动API服务器"""
    try:
        print("\n" + "="*60)
        print("🚀 网易云音乐API服务启动中...")
        print("="*60)
        print(f"📡 服务地址: http://{config.host}:{config.port}")
        print(f"📁 下载目录: {api_service.downloads_path.absolute()}")
        print(f"📋 日志级别: {config.log_level}")

        if config.enable_sync and config.playlist_ids:
            print("\n⏰ 定时同步服务:")
            print(f"  ├─ 启用状态: ✓ 已启用")
            print(f"  ├─ 歌单数量: {len(config.playlist_ids)}")
            print(f"  ├─ 同步音质: {config.sync_quality}")

        print("\n📚 API端点:")
        print(f"  ├─ GET  /health        - 健康检查")
        print(f"  ├─ POST /song          - 获取歌曲信息")
        print(f"  ├─ POST /search        - 搜索音乐")
        print(f"  ├─ POST /playlist      - 获取歌单详情")
        print(f"  ├─ POST /download      - 下载音乐")
        print(f"  ├─ POST /sync/now      - 立即同步")
        print("="*60)
        print(f"⏰ 启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("🌟 服务已就绪，等待请求...\n")

        init_push_routes(app, api_service)

        fire_event(EventType.SERVER_STARTED, {
            'host': config.host, 'port': config.port, 'version': '2.0.0',
        }, source='server', async_mode=True)

        if api_service.sync_service:
            try:
                api_service.sync_service.start()
            except Exception as e:
                api_service.logger.error(f"启动定时同步服务失败: {e}")

        app.run(host=config.host, port=config.port, debug=config.debug, threaded=True)

    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
        if api_service.sync_service:
            api_service.sync_service.stop()
    except Exception as e:
        api_service.logger.error(f"启动服务失败: {e}")
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


# ── 配置加载 ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_settings_json() -> Dict[str, Any]:
    settings_path = _PROJECT_ROOT / 'config' / 'settings.json'
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def parse_env_list(env_var: str, default: str = "") -> List[str]:
    value = os.getenv(env_var, default)
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


settings = load_settings_json()
file_config = load_sync_config_from_file()

config.host = settings.get('host', os.getenv('HOST', '0.0.0.0'))
config.port = int(settings.get('port', os.getenv('PORT', '5000')))
config.debug = settings.get('debug', os.getenv('DEBUG', 'false').lower() == 'true')
config.downloads_dir = settings.get('downloads_dir', os.getenv('DOWNLOADS_DIR', 'downloads'))
config.download_save_local = settings.get('download_save_local', os.getenv('DOWNLOAD_SAVE_LOCAL', 'false').lower() in ('true', '1', 'yes'))
config.download_browser = settings.get('download_browser', os.getenv('DOWNLOAD_BROWSER', 'true').lower() in ('true', '1', 'yes'))
config.log_level = settings.get('log_level', os.getenv('LOG_LEVEL', 'INFO'))
config.max_file_size = int(settings.get('max_file_size', os.getenv('MAX_FILE_SIZE', str(config.max_file_size))))
config.request_timeout = int(settings.get('request_timeout', os.getenv('REQUEST_TIMEOUT', str(config.request_timeout))))
config.enable_sync = file_config.get('enable_sync', settings.get('enable_sync', os.getenv('ENABLE_SYNC', 'false').lower() == 'true'))
config.playlist_ids = file_config.get('playlist_ids', settings.get('playlist_ids', parse_env_list('PLAYLIST_IDS')))
config.sync_quality = file_config.get('sync_quality', settings.get('sync_quality', os.getenv('SYNC_QUALITY', os.getenv('LEVEL', 'lossless'))))
config.sync_interval = int(file_config.get('sync_interval', settings.get('sync_interval', os.getenv('SYNC_INTERVAL', '3600'))))
config.cron_expression = file_config.get('cron_expression', settings.get('cron_expression', os.getenv('CRON_EXPRESSION', ''))) or None
config.download_lyric_save_lrc = settings.get('download_lyric_save_lrc', True)

if __name__ == '__main__':
    start_api_server()
