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

# 将 backend/ 目录添加到 Python 路径，以支持模块导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 项目根目录
_PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent

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


# ==================== 公开歌词查询（无需鉴权，供第三方如音流使用） ====================

@app.route('/api/lyrics', methods=['GET'])
def public_lyrics_query():
    """公开歌词查询接口（代理模式），返回纯文本 LRC

    1. 先查本地 SQLite DB
    2. 未命中则搜索网易云 API → 获取歌词 → 存入本地 DB → 返回
    3. 仍未命中返回空字符串

    Query params:
        title   - 歌曲名
        artist  - 歌手名（可选）
        duration - 当前歌曲总时长(秒)（可选，保留兼容）

    Returns: text/plain 原始 LRC 文本，无 JSON 包装
    """
    import re
    def _fix_ts(text):
        if not text:
            return ''
        return re.sub(r'(\[\d{2}:\d{2}\.\d{2})\d\]', r'\1]', text)

    lrc = ''
    try:
        title = request.args.get('title', '').strip()
        artist = request.args.get('artist', '').strip()

        if not title:
            return Response('', mimetype='text/plain; charset=utf-8')

        # 第1步：查本地 DB
        db = LyricsDB()
        result = db.search_public(title=title, artist=artist)
        if result:
            lrc = result.get('original_lyric', '')
            return Response(_fix_ts(lrc), mimetype='text/plain; charset=utf-8')

        # 第2步：代理网易云 API 搜索 + 获取歌词
        search_keyword = f"{title} {artist}".strip()
        # 从 token 提取用户以确保 cookie 文件路径正确
        token = _extract_token_from_request()
        if token:
            username = verify_token(token)
            if username:
                set_current_user(username)
        api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
        cookies = api_service.cookie_manager.parse_cookies()
        if not cookies:
            return Response('', mimetype='text/plain; charset=utf-8')

        import json as _json
        search_results = search_music(search_keyword, cookies, limit=5)
        if not search_results:
            return Response('', mimetype='text/plain; charset=utf-8')

        # 找到最佳匹配
        matched_song = None
        for song in search_results:
            if song.get('name', '').lower() == title.lower():
                matched_song = song
                break
        if not matched_song:
            matched_song = search_results[0]

        song_id = matched_song.get('id')
        song_name = matched_song.get('name', title)
        song_artist = matched_song.get('artists', artist)

        lyric_result = lyric_v1(song_id, cookies)
        if not lyric_result:
            return Response('', mimetype='text/plain; charset=utf-8')

        lrc = lyric_result.get('lrc', {}).get('lyric', '')
        tlrc = lyric_result.get('tlyric', {}).get('lyric', '')

        # 存入本地 DB
        db.save_lyric(
            song_id=song_id, song_name=song_name, artist=song_artist,
            album='', original_lyric=lrc, translated_lyric=tlrc,
            lyric_raw=_json.dumps(lyric_result, ensure_ascii=False),
        )
        if config.download_lyric_save_lrc:
            from lyrics_db import save_lrc_file
            safe_stem = ''.join(c for c in f"{song_artist} - {song_name}" if c not in r'<>:"/\|?*')
            save_lrc_file(_get_user_downloads_path(), safe_stem, lrc, tlrc)

        api_service.logger.info(f"公开歌词查询代理成功: {title} → song_id={song_id}")

    except Exception as e:
        api_service.logger.error(f"公开歌词查询异常: {e}")

    return Response(_fix_ts(lrc), mimetype='text/plain; charset=utf-8')


# ==================== 音乐口味雷达 API ====================

@app.route('/api/user/<username>/taste-radar', methods=['GET'])
@login_required
def api_taste_radar(username):
    """10 维全景音乐 DNA 谱图 — 物理声学 7 维 + 文化标签 3 维"""
    try:
        db_path = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'config' / 'music_vault.db'
        if not db_path.exists():
            return APIResponse.success({
                'radar': [50] * 10,
                'count': 0
            }, "暂无特征数据")

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # ── 第一步：7 个物理/情感字段 AVG 聚合 ──
        cur = conn.execute("PRAGMA table_info(track_audio_features)")
        columns = {row[1] for row in cur.fetchall()}

        def col_avg(name, fallback=50):
            if name in columns:
                return f"ROUND(AVG(COALESCE(f.{name}, {fallback})))"
            return str(fallback)

        sql_physical = f"""
            SELECT {col_avg('score_tempo')},
                   {col_avg('score_energy')},
                   {col_avg('score_brightness')},
                   {col_avg('score_energy_contrast')},
                   {col_avg('score_sub_bass')},
                   {col_avg('score_vocal_dominant')},
                   {col_avg('score_lyric_sentiment')}
            FROM user_track_behaviors b
            INNER JOIN track_audio_features f ON b.track_id = f.track_id
            WHERE b.username = ? AND b.is_favorite = 1
        """
        cur = conn.execute(sql_physical, (username,))
        row = cur.fetchone()

        physical = [int(v) for v in row] if row else [50] * 7

        # ── 第二步：跨表标签频次归一化 → 3 个文化维度 ──
        # 总收藏曲数
        cur = conn.execute(
            "SELECT COUNT(*) FROM user_track_behaviors WHERE username=? AND is_favorite=1",
            (username,)
        )
        total = cur.fetchone()[0] or 1  # 兜底避免除零

        # 空间氛围感 — PANNs 'Ambient music'，无标签时用物理特征估算
        cur = conn.execute("""
            SELECT COUNT(DISTINCT tt.track_id)
            FROM user_track_behaviors b
            JOIN track_tags tt ON tt.track_id = b.track_id
            WHERE b.username = ? AND b.is_favorite = 1
              AND tt.tag_name = 'Ambient music'
        """, (username,))
        ambiance_count = cur.fetchone()[0] or 0
        if ambiance_count > 0:
            ambiance = min(100, round(ambiance_count / total * 100))
        else:
            # 无 PANNs 标签时：低能量 + 低对比度 ≈ 氛围感强
            ambiance = int(round(
                (100 - physical[1]) * 0.5 + (100 - physical[3]) * 0.5
            ))

        # 纯器乐倾向 — PANNs 'Classical music'，无标签时用物理特征估算
        cur = conn.execute("""
            SELECT COUNT(DISTINCT tt.track_id)
            FROM user_track_behaviors b
            JOIN track_tags tt ON tt.track_id = b.track_id
            WHERE b.username = ? AND b.is_favorite = 1
              AND tt.tag_name = 'Classical music'
        """, (username,))
        instrumental_count = cur.fetchone()[0] or 0
        if instrumental_count > 0:
            instrumental = min(100, round(instrumental_count / total * 100))
        else:
            # 无 PANNs 标签时：低能量 + 低人声主导（ZCR高）≈ 器乐倾向
            # physical[5] = score_vocal_dominant，值越高越偏人声
            vocal_avg = physical[5] if len(physical) > 5 else 50
            instrumental = int(round(
                (100 - physical[1]) * 0.4 + (100 - vocal_avg) * 0.6
            ))

        # 文化主题共鸣 — Ollama LLM 标签（国风/江湖/古风），无标签时用物理特征估算
        cur = conn.execute("""
            SELECT COUNT(DISTINCT tt.track_id)
            FROM user_track_behaviors b
            JOIN track_tags tt ON tt.track_id = b.track_id
            WHERE b.username = ? AND b.is_favorite = 1
              AND tt.category = 'llm'
              AND (tt.tag_name LIKE '%国风%' OR tt.tag_name LIKE '%江湖%' OR tt.tag_name LIKE '%古风%')
        """, (username,))
        cultural_count = cur.fetchone()[0] or 0
        if cultural_count > 0:
            cultural = min(100, round(cultural_count / total * 100))
        else:
            # 无 LLM 标签时：中低能量 + 中等音色 + 偏抒情 ≈ 文化共鸣潜力
            cultural = int(round(
                (100 - physical[1]) * 0.3 + physical[2] * 0.3 + physical[6] * 0.4
            ))

        conn.close()

        radar = physical + [ambiance, instrumental, cultural]

        if total > 0:
            return APIResponse.success({
                'radar': radar,
                'count': total
            }, f"DNA 谱图数据获取成功（{total}首）")
        else:
            return APIResponse.success({
                'radar': [50] * 10,
                'count': 0
            }, "暂无喜欢歌曲数据")

    except Exception as e:
        api_service.logger.error(f"DNA 谱图异常: {e}")
        return APIResponse.success({
            'radar': [50] * 10,
            'count': 0
        }, f"获取失败: {str(e)}")


@app.route('/api/user/<username>/taste-top-tracks', methods=['GET'])
@login_required
def api_taste_top_tracks(username):
    """TOP 10 共鸣单曲 — 7 维物理+情感均值排名"""
    try:
        db_path = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'config' / 'music_vault.db'
        if not db_path.exists():
            return APIResponse.success([], "暂无数据")

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT mt.id AS track_id, mt.title, mt.artist, mt.file_path,
                   ROUND((
                       COALESCE(f.score_tempo,50) + COALESCE(f.score_energy,50) +
                       COALESCE(f.score_brightness,50) + COALESCE(f.score_energy_contrast,50) +
                       COALESCE(f.score_sub_bass,50) + COALESCE(f.score_vocal_dominant,50) +
                       COALESCE(f.score_lyric_sentiment,50)
                   ) / 7.0, 1) AS resonance
            FROM user_track_behaviors b
            INNER JOIN track_audio_features f ON b.track_id = f.track_id
            INNER JOIN music_tracks mt ON mt.id = b.track_id
            WHERE b.username = ? AND b.is_favorite = 1
            ORDER BY resonance DESC
            LIMIT 50
        """, (username,))
        rows = cur.fetchall()
        conn.close()

        tracks = []
        for i, r in enumerate(rows):
            tracks.append({
                'rank': i + 1,
                'track_id': str(r['track_id']),
                'title': r['title'],
                'artist': r['artist'],
                'file_path': r['file_path'],
                'resonance': r['resonance'],
            })
        return APIResponse.success(tracks, f"TOP {len(tracks)} 共鸣单曲")
    except Exception as e:
        api_service.logger.error(f"TOP 共鸣异常: {e}")
        return APIResponse.success([], f"获取失败: {str(e)}")


# ═══════════════════════════════════════════════════════════════
#  DNA 雷达重建（基于我喜欢歌单，3线程并行下载+评分）
# ═══════════════════════════════════════════════════════════════

@app.route('/api/user/<username>/taste-rebuild', methods=['POST'])
@login_required
def api_taste_rebuild(username):
    """触发后台重建 DNA 数据：从我喜欢歌单下载未分析歌曲 → 评分 → 写入 DB"""
    task = task_manager.create_task(
        'dna_rebuild', 'DNA雷达重建',
        username=username,
    )
    thread = threading.Thread(
        target=_dna_rebuild_worker,
        args=(task.task_id, username),
        daemon=True,
        name=f'dna-rebuild-{task.task_id}',
    )
    thread.start()
    return APIResponse.success({'task_id': task.task_id}, "重建任务已启动")


def _dna_rebuild_worker(task_id: str, username: str):
    """3 线程并行下载+分析我喜欢歌单中的歌曲"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        # 获取 liked IDs（优先缓存，未命中则直接拉取）
        global _liked_ids_cache
        liked_ids = _liked_ids_cache
        if not liked_ids:
            liked_ids = _fetch_liked_ids_direct()
            if liked_ids:
                _liked_ids_cache = liked_ids
        if not liked_ids:
            task_manager.update_task(task_id, status=TaskStatus.FAILED,
                                     message='未获取到喜欢歌单', error='liked_ids empty')
            return

        total = len(liked_ids)

        # ── 清空该用户旧的行为数据，确保 taste-radar 只展示本次重建结果 ──
        db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("DELETE FROM user_track_behaviors WHERE username = ?", (username,))
            conn.commit()
            conn.close()
            api_service.logger.info(f"[DNA重建] 已清空 {username} 的旧行为数据")
        except Exception as e:
            api_service.logger.warning(f"[DNA重建] 清空旧数据失败（继续）: {e}")

        task_manager.update_task(task_id, status=TaskStatus.RUNNING,
                                 progress=0, message=f'共 {total} 首，3 线程并行处理中')

        cookies = _pb_load_cookies()
        completed = 0
        skipped = 0
        failed = 0
        cancel_lock = threading.Lock()
        progress_lock = threading.Lock()

        def _check_cancelled() -> bool:
            t = task_manager.get_task(task_id)
            return t is not None and t.status == TaskStatus.CANCELLED

        def _process_one(track_id: int) -> Optional[str]:
            nonlocal completed, skipped, failed
            with cancel_lock:
                if _check_cancelled():
                    return 'cancelled'

            try:
                # ── 1. 本地命中检查（先获取 title+artist 以匹配 DB） ──
                detail = name_v1(track_id) or {}
                songs = detail.get('songs', [])
                if songs:
                    title = songs[0].get('name', f'track_{track_id}')
                    ar = songs[0].get('ar', [])
                    artist = ', '.join(a.get('name', '') for a in ar) if ar else ''
                else:
                    title = f'track_{track_id}'
                    artist = ''

                db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
                conn = sqlite3.connect(str(db_path))
                cur = conn.execute(
                    "SELECT mt.id FROM music_tracks mt "
                    "INNER JOIN track_audio_features f ON mt.id = f.track_id "
                    "WHERE mt.title = ? AND mt.artist = ?",
                    (title, artist),
                )
                existing = cur.fetchone()
                conn.close()
                if existing:
                    # 已有特征的曲目：确保 user_track_behaviors 有记录（清除后需补回）
                    local_tid = existing[0]
                    try:
                        conn2 = sqlite3.connect(str(db_path))
                        conn2.execute(
                            "INSERT OR IGNORE INTO user_track_behaviors (track_id, username) VALUES (?, ?)",
                            (local_tid, username),
                        )
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass
                    with progress_lock:
                        skipped += 1
                        completed += 1
                    return 'skipped'

                # ── 2. 需要下载 → 获取 URL ──
                if not cookies:
                    with progress_lock:
                        failed += 1
                        completed += 1
                    return 'no_cookies'

                from music_api import url_v1
                url_result = url_v1(track_id, 'exhigh', cookies)
                song_url = None
                if isinstance(url_result, dict):
                    data_list = url_result.get('data', [])
                    song_url = data_list[0].get('url', '') if data_list else ''
                # 降级尝试 standard 和 higher
                if not song_url:
                    for q in ('lossless', 'hires', 'standard'):
                        url_result = url_v1(track_id, q, cookies)
                        if isinstance(url_result, dict):
                            data_list = url_result.get('data', [])
                            song_url = data_list[0].get('url', '') if data_list else ''
                        if song_url:
                            break

                if not song_url:
                    with progress_lock:
                        failed += 1
                        completed += 1
                    return 'no_url'

                # ── 3. 下载 + CAS 存储 ──
                from services.song_storage import SongStorageService
                storage = SongStorageService()
                metadata = {'track_id': str(track_id), 'song_name': title}
                try:
                    store_path, _ = storage.download_and_store(
                        username, song_url, metadata,
                    )
                except Exception:
                    with progress_lock:
                        failed += 1
                        completed += 1
                    return 'download_failed'

                # ── 4. 自动评分 ──
                from music_processor.single_scorer import score_single_track
                try:
                    score_single_track(
                        str(store_path),
                        title=title,
                        artist=artist,
                        album='',
                        username=username,
                    )
                except Exception:
                    with progress_lock:
                        failed += 1
                        completed += 1
                    return 'score_failed'

                with progress_lock:
                    completed += 1
                return 'scored'

            except Exception:
                with progress_lock:
                    failed += 1
                    completed += 1
                return 'error'

        # ── 3 线程执行 ──
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {executor.submit(_process_one, tid): tid for tid in liked_ids}
            for future in as_completed(future_map):
                if _check_cancelled():
                    # 尝试取消未开始的
                    for f in future_map:
                        f.cancel()
                    break
                try:
                    future.result()
                except Exception:
                    pass  # 已在 _process_one 内部处理

                with progress_lock:
                    pct = int(completed / total * 100) if total else 0
                    task_manager.update_task(
                        task_id, progress=pct,
                        message=f'{completed}/{total} | 跳过:{skipped} 失败:{failed}'
                    )

        with cancel_lock:
            if _check_cancelled():
                task_manager.update_task(
                    task_id, status=TaskStatus.CANCELLED,
                    message=f'用户取消 | 已处理 {completed}/{total}',
                )
                return

        task_manager.update_task(
            task_id, status=TaskStatus.COMPLETED, progress=100,
            message=f'完成 {completed}/{total} | 跳过:{skipped} 失败:{failed}',
        )
    except Exception as e:
        api_service.logger.error(f"DNA rebuild 异常: {e}")
        task_manager.update_task(task_id, status=TaskStatus.FAILED,
                                 message=f'异常中断', error=str(e))


@app.route('/api/user/<username>/taste-top-tags', methods=['GET'])
@login_required
def api_taste_top_tags(username):
    """高频 AI 标签 — GROUP BY tag_name/category"""
    try:
        db_path = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'config' / 'music_vault.db'
        if not db_path.exists():
            return APIResponse.success([], "暂无数据")

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT tt.tag_name, tt.category,
                   COUNT(*) AS freq,
                   ROUND(AVG(tt.confidence)) AS avg_confidence
            FROM user_track_behaviors b
            JOIN track_tags tt ON tt.track_id = b.track_id
            WHERE b.username = ? AND b.is_favorite = 1
            GROUP BY tt.tag_name, tt.category
            ORDER BY freq DESC
            LIMIT 20
        """, (username,))
        rows = cur.fetchall()
        conn.close()

        tags = [{
            'tag_name': r['tag_name'],
            'category': r['category'],
            'freq': r['freq'],
            'avg_confidence': r['avg_confidence'],
        } for r in rows]
        return APIResponse.success(tags, f"TOP {len(tags)} 标签")
    except Exception as e:
        api_service.logger.error(f"TOP 标签异常: {e}")
        return APIResponse.success([], f"获取失败: {str(e)}")


@app.route('/api/tags/<tag_name>/tracks', methods=['GET'])
@login_required
def api_tag_tracks(tag_name):
    """标签反查歌曲 — 按 confidence 降序"""
    try:
        from urllib.parse import unquote
        tag_name = unquote(tag_name)
        db_path = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'config' / 'music_vault.db'
        if not db_path.exists():
            return APIResponse.success([], "暂无数据")

        username = get_current_user()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT mt.id AS track_id, mt.title, mt.artist, mt.file_path,
                   tt.confidence,
                   CASE WHEN b.is_favorite = 1 THEN 1 ELSE 0 END AS is_favorite
            FROM track_tags tt
            JOIN music_tracks mt ON mt.id = tt.track_id
            LEFT JOIN user_track_behaviors b ON b.track_id = tt.track_id AND b.username = ?
            WHERE tt.tag_name = ?
            ORDER BY tt.confidence DESC
            LIMIT 50
        """, (username or 'admin', tag_name))
        rows = cur.fetchall()
        conn.close()

        tracks = [{
            'track_id': r['track_id'],
            'title': r['title'],
            'artist': r['artist'],
            'file_path': r['file_path'],
            'confidence': r['confidence'],
            'is_favorite': bool(r['is_favorite']),
        } for r in rows]
        return APIResponse.success(tracks, f"标签 '{tag_name}' 关联 {len(tracks)} 首歌曲")
    except Exception as e:
        api_service.logger.error(f"标签反查异常: {e}")
        return APIResponse.success([], f"获取失败: {str(e)}")


# ==================== SPA 前端路由 ====================

@app.route('/api/v3/music/stream/<track_id>', methods=['GET', 'HEAD'])
def api_v3_music_stream(track_id):
    """
    流媒体代理：支持 HTTP Range（可拖动进度条）。

    1. HEAD 获取远端文件大小
    2. 有 Range → 206 Partial Content（仅请求目标字节范围）
    3. 无 Range → 200 全量流式代理
    """
    try:
        cookies = _pb_load_cookies()
        if not cookies:
            return APIResponse.error("无有效 Cookie", 401)

        song_id = int(track_id)
        url_info = url_v1(song_id, 'exhigh', cookies)
        if not url_info or not url_info.get('data') or not url_info['data'][0].get('url'):
            url_info = url_v1(song_id, 'standard', cookies)
            if not url_info or not url_info.get('data') or not url_info['data'][0].get('url'):
                return APIResponse.error("无法获取歌曲播放链接", 404)

        song_url = url_info['data'][0]['url']
        song_type = url_info['data'][0].get('type', 'mp3')
        content_type = f'audio/{song_type}' if song_type else 'audio/mpeg'

        hdrs = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://music.163.com/',
        }

        # ── 获取远端文件大小 ──
        file_size = 0
        try:
            hr = requests.head(song_url, headers=hdrs, timeout=15)
            file_size = int(hr.headers.get('Content-Length', 0))
        except Exception:
            pass

        # ── 解析 Range ──
        range_header = request.headers.get('Range', '')
        range_start, range_end = None, None
        if range_header.startswith('bytes='):
            try:
                v = range_header[6:]
                a, _, b = v.partition('-')
                range_start = int(a) if a else 0
                range_end = int(b) if b else None
            except ValueError:
                pass

        # ── 无 Range 或无法获取大小 → 全量代理 ──
        if range_start is None or file_size <= 0:
            r = requests.get(song_url, headers=hdrs, stream=True, timeout=30)
            r.raise_for_status()
            def _full():
                for c in r.iter_content(chunk_size=65536):
                    yield c
            resp = Response(stream_with_context(_full()), content_type=content_type)
            resp.headers['Accept-Ranges'] = 'bytes'
            if file_size > 0:
                resp.headers['Content-Length'] = str(file_size)
            return resp

        if range_end is None:
            range_end = file_size - 1
        range_start = max(0, range_start)
        range_end = min(file_size - 1, range_end)
        if range_start > range_end:
            return Response("Range Not Satisfiable", status=416)

        content_length = range_end - range_start + 1
        range_hdrs = dict(hdrs)
        range_hdrs['Range'] = f'bytes={range_start}-{range_end}'
        r = requests.get(song_url, headers=range_hdrs, stream=True, timeout=30)

        # 远端支持 Range → 直接转发
        if r.status_code == 206:
            r.raise_for_status()
            def _range():
                sent = 0
                for c in r.iter_content(chunk_size=65536):
                    if sent >= content_length:
                        break
                    yield c
                    sent += len(c)
            resp = Response(stream_with_context(_range()), status=206, content_type=content_type)
        else:
            # 远端不支持 Range → 手动跳转到目标位置
            r = requests.get(song_url, headers=hdrs, stream=True, timeout=30)
            r.raise_for_status()
            skipped = [0]
            def _skip():
                for c in r.iter_content(chunk_size=65536):
                    if skipped[0] < range_start:
                        need = range_start - skipped[0]
                        skipped[0] += len(c)
                        if skipped[0] > range_start:
                            yield c[len(c) - (skipped[0] - range_start):]
                        continue
                    yield c
            resp = Response(stream_with_context(_skip()), status=206, content_type=content_type)

        resp.headers['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
        resp.headers['Content-Length'] = str(content_length)
        resp.headers['Accept-Ranges'] = 'bytes'
        return resp

    except Exception as e:
        api_service.logger.error(f"流媒体代理异常: {e}")
        return APIResponse.error(str(e), 500)


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


# 无需认证的 API 路径白名单
AUTH_WHITELIST = {
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/verify',
    '/api/health',
    '/api/info',
    '/api/lyrics',
}


@app.before_request
def before_request():
    """请求前处理：日志记录 + Token 认证"""
    # 记录请求信息
    api_service.logger.info(
        f"{request.method} {request.path} - IP: {request.remote_addr} - "
        f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
    )

    # OPTIONS 预检请求直接放行
    if request.method == 'OPTIONS':
        return '', 200

    # 仅对 /api/ 路径做认证校验，静态资源放行
    if not request.path.startswith('/api/'):
        return

    # 白名单路径放行
    if request.path in AUTH_WHITELIST:
        return

    # v3 API：不强制拦截，但尝试从 token 提取用户（供 cookie 加载使用）
    if request.path.startswith('/api/v3/'):
        token = _extract_token_from_request()
        if token:
            username = verify_token(token)
            if username:
                set_current_user(username)
        return

    # 验证 Token
    token = _extract_token_from_request()
    if not token:
        return APIResponse.error("未提供认证Token，请先登录", 401)

    username = verify_token(token)
    if not username:
        return APIResponse.error("Token无效或已过期，请重新登录", 401)

    set_current_user(username)


def _extract_token_from_request():
    """从请求中提取 Bearer token"""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    token = request.args.get('token', '')
    if token:
        return token
    return None


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


# ==================== 认证 API ====================

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """用户登录 API

    Request JSON:
        { "username": "admin", "password": "admin123" }

    Response:
        { "status": 200, "success": true, "data": { "token": "...", "username": "admin" } }
    """
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')

        api_service.logger.info(f"[登录请求] 接收到用户名: '{username}', 密码: '{password}'")

        if not username or not password:
            api_service.logger.warning("[登录请求] 用户名或密码为空")
            return APIResponse.error("用户名和密码不能为空", 400)

        if not verify_credentials(username, password):
            api_service.logger.warning(f"[登录请求] 验证失败 - 用户名: '{username}', 密码: '{password}'")
            return APIResponse.error("用户名或密码错误", 401)

        token = generate_token(username)
        set_current_user(username)

        api_service.logger.info(f"用户登录成功: {username}")
        return APIResponse.success({
            'token': token,
            'username': username,
        }, "登录成功")

    except Exception as e:
        api_service.logger.error(f"登录异常: {e}")
        return APIResponse.error(f"登录失败: {str(e)}", 500)


@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    """用户注册 API

    Request JSON:
        { "username": "...", "password": "..." }

    Response (成功):
        { "status": 200, "success": true, "data": { "token": "...", "username": "..." }, "message": "注册成功" }
    """
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return APIResponse.error("用户名和密码不能为空", 400)

        success, message = register_user(username, password)
        if not success:
            return APIResponse.error(message, 409)

        # 注册成功 → 自动签发 Token，进入登录态
        token = generate_token(username)
        set_current_user(username)

        api_service.logger.info(f"用户注册并自动登录: {username}")
        return APIResponse.success({
            'token': token,
            'username': username,
        }, message)

    except Exception as e:
        api_service.logger.error(f"注册异常: {e}")
        return APIResponse.error(f"注册失败: {str(e)}", 500)


@app.route('/api/auth/verify', methods=['GET'])
def auth_verify():
    """验证 Token 有效性

    Headers:
        Authorization: Bearer <token>

    Response:
        { "status": 200, "success": true, "data": { "username": "admin", "valid": true } }
    """
    username = get_current_user()
    if not username:
        return APIResponse.error("Token无效或已过期", 401)

    return APIResponse.success({
        'username': username,
        'valid': True,
    }, "Token有效")


# ==================== API 路由 ====================

@app.route('/api/api-docs', methods=['GET'])
def api_docs_json():
    """API 文档 JSON 端点"""
    try:
        import json
        config_path = _PROJECT_ROOT / 'config' / 'api.json'
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
        logs_dir = _PROJECT_ROOT / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)

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
        logs_dir = _PROJECT_ROOT / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)

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


@app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
def api_task_cancel(task_id):
    """取消正在运行的任务"""
    task = task_manager.get_task(task_id)
    if not task:
        return APIResponse.error("任务不存在", 404)
    if task.status != TaskStatus.RUNNING:
        return APIResponse.error("只能取消运行中的任务", 400)
    task_manager.update_task(task_id, status=TaskStatus.CANCELLED, message='用户取消')
    return APIResponse.success(None, "任务已取消")


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
        source = (data.get('source') or 'netease').strip().lower()  # netease / qq
        
        # 参数验证
        validation_error = api_service._validate_request_params({'keyword': keyword})
        if validation_error:
            return validation_error
        
        # 限制搜索数量
        if limit > 100:
            limit = 100
        
        if source == 'qq':
            # QQ音乐音源搜索（携带用户配置的QQ Cookie以获取完整结果）
            result = qq_search_music(keyword, limit, cookie=_read_qq_cookie())
        else:
            source = 'netease'
            cookies = api_service._get_cookies()
            result = search_music(keyword, cookies, limit)
        
        # search_music返回的是歌曲列表，需要包装成前端期望的格式
        if result:
            for song in result:
                # 标注音源，便于前端区分
                song.setdefault('source', source)
                # 添加艺术家字符串（如果需要）
                if 'artists' in song:
                    song['artist_string'] = song['artists']
        
        fire_event(EventType.SEARCH_PERFORMED, {
            'keyword': keyword,
            'source': source,
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


def _fetch_and_save_lyric(music_id, song_info, cookies, safe_filename='', download_dir=''):
    """获取歌词并保存到 SQLite + 导出 .lrc 文件"""
    try:
        username = get_current_user() or ''
        lyric_result = lyric_v1(music_id, cookies)
        if not lyric_result:
            return

        song_data = song_info.get('songs', [{}])[0] if song_info.get('songs') else {}
        artist_name = ', '.join(a.get('name', '') for a in song_data.get('ar', []))
        album_name = song_data.get('al', {}).get('name', '') if song_data.get('al') else ''
        original_lyric = lyric_result.get('lrc', {}).get('lyric', '')
        translated_lyric = lyric_result.get('tlyric', {}).get('lyric', '')

        db = LyricsDB()
        import json as _json
        db.save_lyric(
            song_id=music_id,
            song_name=song_data.get('name', ''),
            artist=artist_name,
            album=album_name,
            original_lyric=original_lyric,
            translated_lyric=translated_lyric,
            lyric_raw=_json.dumps(lyric_result, ensure_ascii=False),
            username=username,
        )
        # 导出 .lrc 文件到歌曲同目录（受 download_lyric_save_lrc 配置控制）
        if config.download_lyric_save_lrc and safe_filename and download_dir:
            from lyrics_db import save_lrc_file
            lrc_stem = ''.join(c for c in f"{artist_name} - {safe_filename}" if c not in r'<>:"/\|?*')
            save_lrc_file(Path(download_dir), lrc_stem, original_lyric, translated_lyric)
        api_service.logger.debug(f"歌词已保存到 SQLite: {music_id} - {song_data.get('name', '')}")
    except Exception as e:
        api_service.logger.warning(f"保存歌词到 SQLite 失败 (song_id={music_id}): {e}")


def _download_qq_music(songmid, quality, save_local, browser_download, download_dir):
    """QQ音乐音源下载处理

    Args:
        songmid: QQ音乐 songmid
        quality: 统一音质命名（standard/exhigh/lossless/...）
        save_local: 是否保存到本地
        browser_download: 是否浏览器下载
        download_dir: 下载目录(Path)

    Returns:
        Flask 响应对象
    """
    qq_cookie = _read_qq_cookie()
    qq_api = QQMusicAPI(qq_cookie)
    task = task_manager.create_task('download', '下载中...', music_id=songmid, quality=quality)

    fire_event(EventType.DOWNLOAD_STARTED, {
        'music_id': songmid,
        'quality': quality,
        'source': 'qq',
        'task_id': task.task_id,
    }, source='api', async_mode=True)

    try:
        task_manager.update_task(task.task_id, status=TaskStatus.RUNNING, message='正在获取歌曲信息...', progress=10)
        detail = qq_api.get_song_detail(songmid)
        song_name = detail.get('name', 'unknown')
        artist_name = detail.get('artists', '')

        # 获取下载链接（按映射音质并自动降级）
        task_manager.update_task(task.task_id, message='正在获取下载链接...', progress=30)
        qq_quality = map_quality_to_qq(quality)
        url_info = qq_api.get_song_url(songmid, qq_quality)
        download_url = url_info.get('url')
        if not download_url:
            hint = '版权限制或无该音质' if qq_cookie else '需要在「Cookie 管理」中配置 QQ音乐登录 Cookie'
            task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='无法获取下载链接', error=hint)
            return APIResponse.error(f"无法获取QQ音乐下载链接（{hint}）", 404)

        actual_quality = url_info.get('quality', qq_quality)
        file_ext = url_info.get('ext', '.mp3')

        task_manager.update_task(task.task_id, name=song_name, extra={
            'artist': artist_name,
            'album': detail.get('album', ''),
            'quality': actual_quality,
            'source': 'qq',
        })

        # 生成安全文件名（与网易云保持风格一致：艺术家 - 歌曲名 [音质]）
        qq_quality_labels = {'128': '标准', '320': '极高', 'flac': '无损', 'master': '母带'}
        include_quality = getattr(config, 'download_quality_in_filename', True)
        base_name = f"{artist_name} - {song_name}"
        if include_quality:
            safe_name = f"{base_name} [QQ-{qq_quality_labels.get(actual_quality, actual_quality)}]"
        else:
            safe_name = base_name
        safe_name = ''.join(c for c in safe_name if c not in r'<>:"/\|?*')
        filename = f"{safe_name}{file_ext}"

        qq_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': 'https://y.qq.com/',
        }

        # 模式 3: 仅保存到本地，后台下载 + JSON 通知
        if save_local and not browser_download:
            file_path = download_dir / filename
            if file_path.exists():
                task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED, message='文件已存在', progress=100)
                operation_logger.info(f"[音乐下载] 音源=QQ MID={songmid} 歌名={song_name} 歌手={artist_name} 音质={actual_quality} (文件已存在)")
                fire_event(EventType.DOWNLOAD_COMPLETED, {
                    'music_id': songmid, 'song_name': song_name, 'artist': artist_name,
                    'quality': actual_quality, 'source': 'qq', 'mode': 'local_only',
                }, source='api', async_mode=True)
            else:
                task_manager.update_task(task.task_id, message='正在后台下载...', progress=50)

                def _bg_download():
                    try:
                        r = requests.get(download_url, headers=qq_headers, stream=True, timeout=60)
                        r.raise_for_status()
                        with open(file_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                        task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED, message='下载完成', progress=100)
                        operation_logger.info(f"[音乐下载] 音源=QQ MID={songmid} 歌名={song_name} 歌手={artist_name} 音质={actual_quality} (仅本地)")
                        fire_event(EventType.DOWNLOAD_COMPLETED, {
                            'music_id': songmid, 'song_name': song_name, 'artist': artist_name,
                            'quality': actual_quality, 'source': 'qq', 'mode': 'local_only',
                        }, source='api', async_mode=True)
                    except Exception as e:
                        task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='下载失败', error=str(e))
                        fire_event(EventType.DOWNLOAD_FAILED, {
                            'music_id': songmid, 'song_name': song_name, 'artist': artist_name,
                            'source': 'qq', 'error': str(e),
                        }, source='api', async_mode=True)
                Thread(target=_bg_download, daemon=True).start()

            response_data = {
                'music_id': songmid, 'name': song_name, 'artist': artist_name,
                'album': detail.get('album', ''), 'quality': actual_quality,
                'source': 'qq', 'filename': filename, 'mode': 'local_only',
            }
            return APIResponse.success(response_data, "已开始后台保存到本地")

        # 模式 1 & 2: 流式代理（浏览器即时下载 + 可选本地保存）
        if save_local:
            file_path = download_dir / filename
            local_f = open(file_path, 'wb')
        else:
            local_f = None

        def stream_proxy():
            try:
                r = requests.get(download_url, headers=qq_headers, stream=True, timeout=60)
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=65536):
                    if local_f:
                        local_f.write(chunk)
                    yield chunk
                task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED, message='下载完成', progress=100)
                tag = " (保存+浏览器)" if save_local else " (仅浏览器)"
                operation_logger.info(f"[音乐下载] 音源=QQ MID={songmid} 歌名={song_name} 歌手={artist_name} 音质={actual_quality}{tag}")
                fire_event(EventType.DOWNLOAD_COMPLETED, {
                    'music_id': songmid, 'song_name': song_name, 'artist': artist_name,
                    'quality': actual_quality, 'source': 'qq',
                    'mode': 'browser' if not save_local else 'both',
                }, source='api', async_mode=True)
            except Exception as e:
                api_service.logger.error(f"QQ流式下载异常: {e}")
                task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='下载失败', error=str(e))
                fire_event(EventType.DOWNLOAD_FAILED, {
                    'music_id': songmid, 'song_name': song_name, 'artist': artist_name,
                    'source': 'qq', 'error': str(e),
                }, source='api', async_mode=True)
            finally:
                if local_f:
                    local_f.close()

        mime_ext = file_ext.lstrip('.')
        resp = Response(stream_with_context(stream_proxy()), mimetype=f"audio/{mime_ext}")
        resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
        resp.headers['X-Download-Filename'] = quote(filename, safe='')
        return resp

    except QQAPIException as e:
        task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='下载失败', error=str(e))
        return APIResponse.error(f"QQ音乐下载失败: {str(e)}", 502)
    except Exception as e:
        task_manager.update_task(task.task_id, status=TaskStatus.FAILED, message='下载过程出错', error=str(e))
        api_service.logger.error(f"QQ音乐下载异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"QQ音乐下载异常: {str(e)}", 500)


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
        source = (data.get('source') or 'netease').strip().lower()  # netease / qq

        # 读取下载配置
        save_local = config.download_save_local
        browser_download = config.download_browser
        download_dir = _get_user_downloads_path()
        
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
        
        # QQ音乐音源：songmid 为字母数字，单独处理，不走网易云数字ID流程
        if source == 'qq':
            return _download_qq_music(str(music_id).strip(), quality, save_local, browser_download, download_dir)
        
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
            
            # 获取歌词并保存到 SQLite + .lrc 文件
            song_data = song_info.get('songs', [{}])[0] if song_info.get('songs') else {}
            song_name_raw = song_data.get('name', 'unknown')
            safe_name = ''.join(c for c in song_name_raw if c not in r'<>:"/\|?*')
            _fetch_and_save_lyric(music_id, song_info, cookies, safe_name, str(download_dir))

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
            
            # 生成安全文件名（与 music_downloader.py 保持一致：艺术家 - 歌曲名 [音质]）
            quality_labels = {'standard':'标准','exhigh':'极高','lossless':'无损','hires':'Hi-Res','sky':'环绕声','jyeffect':'高清环绕','jymaster':'母带'}
            include_quality = getattr(config, 'download_quality_in_filename', True)
            base_name = f"{artist_name} - {music_info['name']}"
            if include_quality:
                safe_name = f"{base_name} [{quality_labels.get(actual_quality, actual_quality)}]"
            else:
                safe_name = base_name
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
            # 使用 RFC 5987 编码避免中文文件名 latin-1 编码错误
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
                '/api/api-docs': 'GET - API文档JSON',
                '/api/lyrics': 'GET - 获取已保存歌词列表',
                '/api/lyrics/search': 'GET - 搜索歌词',
                '/api/lyrics/<song_id>': 'GET - 获取指定歌曲歌词',
                '/api/lyrics/<song_id>': 'DELETE - 删除指定歌曲歌词',
                '/api/lyrics/count': 'GET - 获取歌词总数',
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


# ==================== 歌词数据库 API ====================

def _get_lyrics_db() -> LyricsDB:
    """获取歌词数据库实例（单库，通过 set_user 设置当前用户）"""
    db = LyricsDB()
    db.set_user(get_current_user() or '')
    return db


@app.route('/api/lyrics/list', methods=['GET'])
def get_lyrics_list():
    """获取所有已保存的歌词列表（分页）"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        db = _get_lyrics_db()
        items, total = db.get_all_lyrics(limit=limit, offset=offset)
        return APIResponse.success({
            'items': items,
            'total': total,
            'limit': limit,
            'offset': offset,
        }, "获取歌词列表成功")
    except Exception as e:
        return APIResponse.error(f"获取歌词列表失败: {str(e)}", 500)


@app.route('/api/lyrics/search', methods=['GET'])
def search_lyrics_api():
    """搜索歌词"""
    try:
        keyword = request.args.get('keyword', '')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        if not keyword:
            return APIResponse.error("请提供搜索关键词")
        db = _get_lyrics_db()
        items, total = db.search_lyrics(keyword, limit=limit, offset=offset)
        return APIResponse.success({
            'items': items,
            'total': total,
            'keyword': keyword,
        }, "搜索歌词成功")
    except Exception as e:
        return APIResponse.error(f"搜索歌词失败: {str(e)}", 500)


@app.route('/api/lyrics/<int:song_id>', methods=['GET'])
def get_lyric_by_id(song_id):
    """根据歌曲 ID 获取歌词"""
    try:
        db = _get_lyrics_db()
        lyric = db.get_lyric(song_id)
        if lyric:
            return APIResponse.success(lyric, "获取歌词成功")
        return APIResponse.error(f"未找到歌曲 {song_id} 的歌词", 404)
    except Exception as e:
        return APIResponse.error(f"获取歌词失败: {str(e)}", 500)


@app.route('/api/lyrics/<int:song_id>', methods=['DELETE'])
def delete_lyric_api(song_id):
    """删除指定歌曲的歌词"""
    try:
        db = _get_lyrics_db()
        db.delete_lyric(song_id)
        return APIResponse.success(None, f"歌词 {song_id} 已删除")
    except Exception as e:
        return APIResponse.error(f"删除歌词失败: {str(e)}", 500)


@app.route('/api/lyrics/count', methods=['GET'])
def get_lyrics_count():
    """获取歌词总数"""
    try:
        db = _get_lyrics_db()
        count = db.get_count()
        return APIResponse.success({'count': count}, "获取歌词总数成功")
    except Exception as e:
        return APIResponse.error(f"获取歌词总数失败: {str(e)}", 500)


@app.route('/api/lyrics/query', methods=['GET', 'POST'])
def query_lyrics_api():
    """歌词查询接口：按歌曲 ID 或中文名称查询歌词（含原文 + 翻译）

    请求参数（任选其一）：
        id      - 歌曲 ID（优先，精确）
        keyword - 歌曲名称 / 关键词（可配合 artist 提高匹配度）
        artist  - 歌手名（可选，仅 keyword 模式生效）

    返回：歌曲元信息 + 原文歌词 lyric + 翻译歌词 tlyric
    """
    try:
        data = api_service._safe_get_request_data()
        song_id = data.get('id') or data.get('ids')
        keyword = data.get('keyword') or data.get('title') or data.get('name')
        artist = (data.get('artist') or '').strip()

        if not song_id and not keyword:
            return APIResponse.error("必须提供 'id' 或 'keyword' 参数")

        cookies = api_service._get_cookies()

        # 名称查询：先搜索匹配最佳歌曲
        if not song_id:
            search_keyword = f"{keyword} {artist}".strip()
            results = search_music(search_keyword, cookies, limit=10)
            if not results:
                return APIResponse.error(f"未搜索到歌曲：{keyword}", 404)
            matched = None
            for song in results:
                if song.get('name', '').lower() == str(keyword).lower():
                    matched = song
                    break
            matched = matched or results[0]
            song_id = matched.get('id')

        music_id = api_service._extract_music_id(song_id)

        # 歌曲元信息
        song_meta = name_v1(music_id)
        song_name, ar_name, al_name, pic = '', '', '', ''
        if song_meta and song_meta.get('songs'):
            sd = song_meta['songs'][0]
            song_name = sd.get('name', '')
            ar_name = ', '.join(a.get('name', '') for a in sd.get('ar', []))
            al_name = sd.get('al', {}).get('name', '')
            pic = sd.get('al', {}).get('picUrl', '')

        # 歌词
        lyric_info = lyric_v1(music_id, cookies)
        lyric = lyric_info.get('lrc', {}).get('lyric', '') if lyric_info else ''
        tlyric = lyric_info.get('tlyric', {}).get('lyric', '') if lyric_info else ''

        if not lyric:
            return APIResponse.error("未找到该歌曲的歌词", 404)

        fire_event(EventType.SONG_INFO_FETCHED, {
            'music_id': music_id,
            'info_type': 'lyric_query',
            'song_name': song_name,
            'artist': ar_name,
        }, source='api')

        return APIResponse.success({
            'id': music_id,
            'name': song_name,
            'ar_name': ar_name,
            'al_name': al_name,
            'pic': pic,
            'lyric': lyric,
            'tlyric': tlyric,
        }, "获取歌词成功")

    except APIException as e:
        api_service.logger.error(f"歌词查询API调用失败: {e}")
        return APIResponse.error(f"API调用失败: {str(e)}", 500)
    except Exception as e:
        api_service.logger.error(f"歌词查询异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"服务器错误: {str(e)}", 500)


@app.route('/api/sync/config', methods=['GET'])
def get_sync_config():
    """获取同步配置"""
    try:
        # 优先读取用户专属配置
        file_config = load_sync_config_from_file()
        if file_config:
            config_data = file_config
        else:
            config_data = {
                'enable_sync': config.enable_sync,
                'playlist_ids': config.playlist_ids,
                'sync_quality': config.sync_quality,
                'sync_interval': config.sync_interval,
                'cron_expression': config.cron_expression or '',
                'sync_full_delete': getattr(config, 'sync_full_delete', False),
                'sync_dedup_files': getattr(config, 'sync_dedup_files', False)
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

        # 即使服务未初始化，也返回配置信息
        if not sync_service:
            file_config = load_sync_config_from_file()
            return APIResponse.success({
                'service_running': False,
                'job_count': 0,
                'config': {
                    'playlist_ids': file_config.get('playlist_ids', config.playlist_ids),
                    'quality': file_config.get('sync_quality', config.sync_quality),
                    'sync_interval': file_config.get('sync_interval', config.sync_interval),
                    'cron_expression': file_config.get('cron_expression', config.cron_expression or ''),
                    'download_dir': str(config.downloads_dir)
                }
            }, "同步服务未运行（配置已保存）")

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

        # 如果服务未初始化但用户配置已启用，从用户配置初始化
        if not sync_service:
            file_config = load_sync_config_from_file()
            if file_config.get('enable_sync') and file_config.get('playlist_ids'):
                api_service.reload_sync_config(file_config)
                sync_service = get_sync_service()

        if not sync_service:
            return APIResponse.error("同步服务未启用，请先在配置页保存同步配置", 400)

        # 同步执行并返回结果（前端需要即时错误反馈）
        results = sync_service.sync_all_playlists()

        success_count = sum(1 for r in results if r.get('success'))
        fail_count = len(results) - success_count
        total_synced = sum(r.get('synced_count', 0) for r in results)

        errors = []
        for r in results:
            if not r.get('success'):
                errors.append({
                    'playlist_id': r.get('playlist_id', ''),
                    'error': r.get('error', '未知错误'),
                })

        return APIResponse.success({
            'success_count': success_count,
            'fail_count': fail_count,
            'total_synced': total_synced,
            'errors': errors,
        }, f"同步完成: 成功 {success_count}/{len(results)}, 下载 {total_synced} 首" + (f", {fail_count} 个失败" if fail_count else ""))
        
    except Exception as e:
        api_service.logger.error(f"触发同步异常: {e}")
        return APIResponse.error(f"触发同步失败: {str(e)}", 500)


@app.route('/api/cookie', methods=['GET'])
def get_cookie_config():
    """获取所有命名 Cookie 列表"""
    try:
        username = get_current_user()
        if username:
            api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
        cookies = api_service.cookie_manager.list_cookies()
        active = api_service.cookie_manager.get_active_cookie_name()
        return APIResponse.success({
            'cookies': cookies,
            'active': active,
            'content': api_service.cookie_manager.read_cookie(),
        }, "获取Cookie配置成功")
    except Exception as e:
        api_service.logger.error(f"获取Cookie配置异常: {e}")
        return APIResponse.error(f"获取Cookie配置失败: {str(e)}", 500)


@app.route('/api/cookie', methods=['POST'])
def save_cookie_config():
    """保存一个命名 Cookie"""
    try:
        username = get_current_user()
        if username:
            api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
        data = api_service._safe_get_request_data()
        cookie_name = (data.get('name') or '默认').strip()
        cookie_content = (data.get('cookie') or data.get('content') or '').strip()

        if not cookie_content:
            return APIResponse.error("Cookie内容不能为空", 400)

        api_service.cookie_manager.save_named_cookie(cookie_name, cookie_content)

        fire_event(EventType.COOKIE_UPDATED, {
            'name': cookie_name,
            'has_content': bool(cookie_content),
        }, source='api')

        return APIResponse.success({
            'name': cookie_name,
            'saved': True
        }, f"Cookie [{cookie_name}] 保存成功")
    except Exception as e:
        api_service.logger.error(f"保存Cookie配置异常: {e}")
        return APIResponse.error(f"保存Cookie配置失败: {str(e)}", 500)


@app.route('/api/cookie/activate', methods=['POST'])
def activate_cookie():
    """激活指定的 Cookie"""
    try:
        username = get_current_user()
        if username:
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
    """删除指定的 Cookie"""
    try:
        username = get_current_user()
        if username:
            api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
        api_service.cookie_manager.delete_cookie(name)
        return APIResponse.success(None, f"Cookie [{name}] 已删除")
    except Exception as e:
        return APIResponse.error(f"删除失败: {str(e)}", 500)


@app.route('/api/qq/cookie', methods=['GET'])
def get_qq_cookie_config():
    """获取QQ音乐 Cookie 配置"""
    try:
        content = _read_qq_cookie()
        return APIResponse.success({
            'content': content,
            'configured': bool(content),
        }, "获取QQ音乐Cookie成功")
    except Exception as e:
        return APIResponse.error(f"获取QQ音乐Cookie失败: {str(e)}", 500)


@app.route('/api/qq/cookie', methods=['POST'])
def save_qq_cookie_config():
    """保存QQ音乐 Cookie 配置（用于QQ音源的完整搜索与下载）"""
    try:
        data = api_service._safe_get_request_data()
        content = (data.get('content') or '').strip()
        _write_qq_cookie(content)
        return APIResponse.success({'configured': bool(content)},
                                   "QQ音乐Cookie已保存" if content else "QQ音乐Cookie已清空")
    except Exception as e:
        return APIResponse.error(f"保存QQ音乐Cookie失败: {str(e)}", 500)


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取下载等通用配置"""
    try:
        return APIResponse.success({
            'downloads_dir': config.downloads_dir,
            'download_save_local': config.download_save_local,
            'download_browser': config.download_browser,
            'download_default_quality': getattr(config, 'download_default_quality', 'lossless'),
            'download_quality_in_filename': getattr(config, 'download_quality_in_filename', True),
            'download_lyric_save_lrc': getattr(config, 'download_lyric_save_lrc', True),
        }, "获取配置成功")
    except Exception as e:
        return APIResponse.error(f"获取配置失败: {str(e)}", 500)


@app.route('/api/settings', methods=['POST'])
def save_settings():
    """保存下载等通用配置到用户专属 settings.json"""
    try:
        data = api_service._safe_get_request_data()

        if 'downloads_dir' in data:
            config.downloads_dir = data['downloads_dir']
        if 'download_save_local' in data:
            config.download_save_local = str(data['download_save_local']).lower() in ('true', '1', 'yes')
        if 'download_browser' in data:
            config.download_browser = str(data['download_browser']).lower() in ('true', '1', 'yes')
        if 'download_default_quality' in data:
            config.download_default_quality = data['download_default_quality']
        if 'download_quality_in_filename' in data:
            config.download_quality_in_filename = str(data['download_quality_in_filename']).lower() in ('true', '1', 'yes')
        if 'download_lyric_save_lrc' in data:
            config.download_lyric_save_lrc = str(data['download_lyric_save_lrc']).lower() in ('true', '1', 'yes')

        # 保存到用户专属 settings.json
        settings_path = Path(_get_user_settings_path())
        current = {}
        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                current = json.load(f)
        current['downloads_dir'] = config.downloads_dir
        current['download_save_local'] = config.download_save_local
        current['download_browser'] = config.download_browser
        current['download_default_quality'] = getattr(config, 'download_default_quality', 'lossless')
        current['download_quality_in_filename'] = getattr(config, 'download_quality_in_filename', True)
        current['download_lyric_save_lrc'] = getattr(config, 'download_lyric_save_lrc', True)
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
            'download_default_quality': getattr(config, 'download_default_quality', 'lossless'),
            'download_quality_in_filename': getattr(config, 'download_quality_in_filename', True),
            'download_lyric_save_lrc': getattr(config, 'download_lyric_save_lrc', True),
        }, "配置保存成功")
    except Exception as e:
        api_service.logger.error(f"保存配置异常: {e}")
        return APIResponse.error(f"保存配置失败: {str(e)}", 500)


# ==================== 推荐排序 API v3 (动态时间权重) ====================

# 全局推荐引擎实例（懒加载）
_rec_engine = None

def _get_rec_engine():
    global _rec_engine
    if _rec_engine is None:
        _rec_engine = get_recommendation_engine()
    return _rec_engine


@app.route('/api/v3/config/weights', methods=['GET'])
def v3_get_weights():
    """读取完整权重配置"""
    try:
        engine = _get_rec_engine()
        config_data = engine.get_config()
        return APIResponse.success(config_data, "权重配置获取成功")
    except Exception as e:
        api_service.logger.error(f"获取权重配置异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"获取失败: {str(e)}", 500)


@app.route('/api/v3/config/weights', methods=['POST'])
def v3_save_weights():
    """覆盖写入权重配置"""
    try:
        data = api_service._safe_get_request_data()
        engine = _get_rec_engine()
        ok, msg = engine.save_config(data)
        if not ok:
            return APIResponse.error(msg, 400)
        return APIResponse.success(None, msg)
    except Exception as e:
        api_service.logger.error(f"保存权重配置异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"保存失败: {str(e)}", 500)


@app.route('/api/v3/recommend/rank', methods=['POST'])
def v3_recommend_rank():
    """
    接收歌曲列表，按当前时段权重排序。

    Request JSON:
        {
            "tracks": [
                {
                    "track_id": "123",
                    "title": "歌名",
                    "artist": "歌手",
                    "features": { "tempo": 70, "energy": 55, ... }
                }
            ],
            "hour": 14,    // 可选，指定小时
            "slot": "daytime"  // 可选，指定时段
        }
    """
    try:
        data = api_service._safe_get_request_data()
        tracks_input = data.get('tracks', [])

        if not tracks_input or not isinstance(tracks_input, list):
            return APIResponse.error("请提供 'tracks' 列表", 400)

        engine = _get_rec_engine()
        hour = data.get('hour')
        slot = data.get('slot')

        if hour is not None:
            hour = int(hour)
        if slot and slot not in SLOT_HOUR_RANGES:
            return APIResponse.error(f"无效时段 '{slot}'，有效值: {sorted(SLOT_HOUR_RANGES.keys())}", 400)

        ranked = engine.rank_tracks_to_dict(tracks_input, hour=hour, slot=slot)

        return APIResponse.success({
            'ranked': ranked,
            'total': len(ranked),
            'applied_slot': ranked[0]['applied_slot'] if ranked else None,
            'slot_label': ranked[0]['slot_label'] if ranked else None,
        }, "推荐排序完成")
    except ValueError as e:
        return APIResponse.error(str(e), 400)
    except Exception as e:
        api_service.logger.error(f"推荐排序异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"排序失败: {str(e)}", 500)


@app.route('/api/v3/recommend/rank-radar', methods=['POST'])
def v3_recommend_rank_radar():
    """
    接收雷达数组格式，自动转为引擎消费格式后排序。

    Request JSON:
        {
            "tracks": [
                { "radar": [70,55,80,60,45,30,20,40,50,65], "track_id": "123", "title": "...", "artist": "..." }
            ],
            "hour": 14,
            "slot": "daytime"
        }
    """
    try:
        data = api_service._safe_get_request_data()
        tracks_input = data.get('tracks', [])

        if not tracks_input or not isinstance(tracks_input, list):
            return APIResponse.error("请提供 'tracks' 列表", 400)

        engine = _get_rec_engine()

        # 将雷达数组转为引擎消费格式
        converted = []
        for t in tracks_input:
            radar = t.get('radar', [])
            if len(radar) != len(FEATURE_KEYS):
                return APIResponse.error(
                    f"歌曲 '{t.get('track_id', '?')}' 雷达数组长度应为 {len(FEATURE_KEYS)}，实际为 {len(radar)}", 400
                )
            converted.append(engine.build_track_from_radar(radar, {
                'track_id': t.get('track_id', ''),
                'title': t.get('title', ''),
                'artist': t.get('artist', ''),
            }))

        hour = data.get('hour')
        slot = data.get('slot')
        if hour is not None:
            hour = int(hour)

        ranked = engine.rank_tracks_to_dict(converted, hour=hour, slot=slot)

        return APIResponse.success({
            'ranked': ranked,
            'total': len(ranked),
            'applied_slot': ranked[0]['applied_slot'] if ranked else None,
            'slot_label': ranked[0]['slot_label'] if ranked else None,
        }, "雷达排序完成")
    except ValueError as e:
        return APIResponse.error(str(e), 400)
    except Exception as e:
        api_service.logger.error(f"雷达排序异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"排序失败: {str(e)}", 500)


@app.route('/api/v3/recommend/slot', methods=['GET'])
def v3_get_slot():
    """查询当前时段及对应权重"""
    try:
        engine = _get_rec_engine()
        info = engine.get_current_slot_info()
        return APIResponse.success(info, "时段查询成功")
    except Exception as e:
        api_service.logger.error(f"时段查询异常: {e}\n{traceback.format_exc()}")
        return APIResponse.error(f"查询失败: {str(e)}", 500)


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
        downloads_dir = _get_user_downloads_path()
        files = []
        for f in sorted(downloads_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file():
                stat = f.stat()
                files.append({
                    'name': f.name,
                    'size': stat.st_size,
                    'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                })
        return APIResponse.success({'files': files}, "文件列表获取成功")
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
        file_path = _get_user_downloads_path() / filename
        # 安全检查：确保文件在 downloads 目录内
        if not file_path.resolve().is_relative_to(_get_user_downloads_path().resolve()):
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
    """流式传输文件（用于音频播放和下载）

    支持多种查找方式（按优先级）：
    1. 直接路径：文件存在 → 直接流式传输
    2. CAS 存储：按 basename 在 user_song_files 中查找 content_hash
    3. CAS 存储：按 title+artist 反查 music_tracks.file_path → CAS hash
    """
    try:
        downloads_dir = _PROJECT_ROOT / 'downloads'
        downloads_root = downloads_dir.resolve()

        # ── Step 1: 尝试直接路径 ──
        file_path = Path(filename)
        if file_path.is_absolute():
            if file_path.exists():
                try:
                    if file_path.resolve().is_relative_to(downloads_root):
                        file_path = file_path.resolve()
                    else:
                        return APIResponse.error("文件不在允许的目录中", 403)
                except (ValueError, OSError):
                    return APIResponse.error("无法解析文件路径", 400)
        else:
            file_path = (downloads_dir / filename).resolve()
            if not file_path.exists():
                file_path = None

        # ── Step 2: 直接路径不存在 → CAS 查找 ──
        if file_path is None or not file_path.exists():
            try:
                from services.song_storage import get_song_storage_service
                storage = get_song_storage_service()
                user = get_current_user() or 'admin'

                # 提取纯文件名（去除 Windows 绝对路径前缀）
                search_name = Path(filename).name  # e.g. "RAYE - Hotbox.mp3"

                # 2a: 按 original_filename 查找用户映射
                songs = storage.get_user_songs(user)
                found_hash = None
                for s in songs:
                    orig = s.get('original_filename', '')
                    if orig == search_name or Path(orig).name == search_name:
                        found_hash = s['content_hash']
                        break

                # 2b: 按 music_tracks 反查
                if not found_hash:
                    import sqlite3
                    db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
                    try:
                        conn = sqlite3.connect(str(db_path))
                        conn.row_factory = sqlite3.Row
                        row = conn.execute(
                            "SELECT file_path FROM music_tracks WHERE file_path LIKE ? LIMIT 1",
                            (f"%{search_name}",),
                        ).fetchone()
                        conn.close()
                        if row:
                            old_path = row['file_path']
                            # 尝试用旧路径的 basename 再次查找
                            for s in songs:
                                if s.get('original_filename', '') == Path(old_path).name:
                                    found_hash = s['content_hash']
                                    break
                    except Exception:
                        pass

                if found_hash and storage.store.has_content(found_hash):
                    ext = storage.store._index.get(found_hash, {}).get('ext', 'mp3')
                    store_path = storage.store.resolve_path(found_hash, ext)
                    if store_path.exists():
                        file_path = store_path

            except ImportError:
                pass

        # ── 最终检查 ──
        if file_path is None or not file_path.exists():
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
        file_path = _get_user_downloads_path() / filename
        if not file_path.resolve().is_relative_to(_get_user_downloads_path().resolve()):
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
        file_path = _get_user_downloads_path() / filename
        if not file_path.resolve().is_relative_to(_get_user_downloads_path().resolve()):
            return APIResponse.error("非法文件路径", 403)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        api_service.logger.info(f"文件已保存: {filename}")
        return APIResponse.success({'filename': filename}, "文件保存成功")
    except Exception as e:
        return APIResponse.error(f"保存文件失败: {str(e)}", 500)


# ═══════════════════════════════════════════════════════════════
#  v3 API — 权重配置 / 推荐排序 / 播放历史 / 推荐流
#  全部运行在 Flask :5000，无需额外 FastAPI 服务
# ═══════════════════════════════════════════════════════════════

@app.route('/api/v3/config/weights', methods=['GET', 'POST'])
def api_v3_weights():
    """读取/保存权重配置"""
    engine = _get_recommendation_engine()
    if request.method == 'GET':
        try:
            config = engine.get_config()
            return APIResponse.success(config, "ok")
        except Exception as e:
            return APIResponse.error(str(e), 500)
    else:
        try:
            data = api_service._safe_get_request_data()
            ok, msg = engine.save_config(data)
            if not ok:
                return APIResponse.error(msg, 400)
            return APIResponse.success(None, msg)
        except Exception as e:
            return APIResponse.error(str(e), 500)


@app.route('/api/v3/recommend/slot', methods=['GET'])
def api_v3_slot():
    """查询当前时段及权重"""
    try:
        engine = _get_recommendation_engine()
        info = engine.get_current_slot_info()
        return APIResponse.success(info, "ok")
    except Exception as e:
        return APIResponse.error(str(e), 500)


@app.route('/api/v3/music/log', methods=['POST'])
def api_v3_music_log():
    """上报播放行为"""
    import sqlite3
    from datetime import datetime, timezone
    try:
        data = api_service._safe_get_request_data()
        track_id = data.get('track_id', '')
        title = data.get('title', '')
        artist = data.get('artist', '')
        play_duration = float(data.get('play_duration', 0))
        total_duration = float(data.get('total_duration', 0))
        source_type = data.get('source_type', '')

        is_skipped = False
        skip_ratio = 0.0
        if total_duration > 0:
            skip_ratio = play_duration / total_duration
            is_skipped = skip_ratio < 0.2

        db_path = str(_PROJECT_ROOT / 'config' / 'music_vault.db')
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("""
                INSERT INTO playback_logs (user_id, track_id, title, artist,
                    play_duration, total_duration, is_skipped, source_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                get_current_user() or 'admin', track_id, title, artist,
                play_duration, total_duration, int(is_skipped), source_type,
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()
            return APIResponse.success({
                'is_skipped': is_skipped,
                'skip_ratio': round(skip_ratio, 3),
            }, "已记录")
        finally:
            conn.close()
    except Exception as e:
        return APIResponse.error(str(e), 500)


@app.route('/api/v3/music/history', methods=['GET'])
def api_v3_music_history():
    """分页返回播放历史"""
    import sqlite3
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        user_id = get_current_user() or 'admin'
        db_path = str(_PROJECT_ROOT / 'config' / 'music_vault.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM playback_logs WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                "SELECT * FROM playback_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset),
            ).fetchall()
            items = []
            for r in rows:
                items.append({
                    'id': r['id'], 'track_id': r['track_id'],
                    'title': r['title'], 'artist': r['artist'],
                    'play_duration': r['play_duration'], 'total_duration': r['total_duration'],
                    'is_skipped': bool(r['is_skipped']), 'timestamp': r['timestamp'],
                })
            return APIResponse.success({
                'total': total, 'page': page, 'page_size': page_size, 'items': items,
            }, "ok")
        finally:
            conn.close()
    except Exception as e:
        return APIResponse.error(str(e), 500)


@app.route('/api/v3/music/recommend', methods=['GET'])
def api_v3_music_recommend():
    """
    推荐接口（分页）。

    - hot_list: 网易云热榜（仅热榜歌曲，本地有则自动匹配特征）
    - custom_playlist: 自定义歌单（仅歌单歌曲，本地有则自动匹配特征）
    - local_library: 本地音乐库（仅本地已分析歌曲）
    - page / page_size: 分页参数
    """
    try:
        source_type = request.args.get('source_type', 'hot_list')
        playlist_id = request.args.get('playlist_id', None)
        sort_order = request.args.get('sort_order', 'desc')
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)

        if source_type not in ('hot_list', 'custom_playlist', 'local_library', 'liked'):
            return APIResponse.error("source_type 仅支持 hot_list / custom_playlist / local_library / liked", 400)
        if source_type == 'custom_playlist' and not playlist_id:
            return APIResponse.error("custom_playlist 必须提供 playlist_id", 400)
        if sort_order not in ('asc', 'desc'):
            sort_order = 'desc'
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 200:
            page_size = 50

        username = get_current_user() or 'admin'

        # ══════════ 分支：本地音乐库 ══════════
        if source_type == 'local_library':
            local_tracks = _get_local_top_tracks(username, limit=50)
            tracks = _build_recommend_tracks(
                [], source_type, '本地音乐库',
                local_tracks=local_tracks,
            )
            tracks = _sort_tracks_by_preference(tracks, sort_order)
            total = len(tracks)
            total_pages = max(1, (total + page_size - 1) // page_size)
            paged = tracks[(page - 1) * page_size : page * page_size]
            return APIResponse.success({
                'total': total, 'page': page, 'page_size': page_size,
                'total_pages': total_pages,
                'source_type': source_type,
                'source_label': '本地音乐库',
                'generated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                'tracks': [t.model_dump() for t in paged],
            }, "ok")

        # ══════════ 分支：我喜欢的音乐 ══════════
        if source_type == 'liked':
            cookies = _pb_load_cookies()
            if not cookies:
                return APIResponse.error("需要配置网易云 Cookie", 400)
            try:
                from music_api import user_account, user_playlist, playlist_detail
                account = user_account(cookies)
                uid = account.get('account', {}).get('id', 0)
                if not uid:
                    return APIResponse.error("未登录网易云账号", 400)
                playlists = user_playlist(uid, cookies, limit=50)
                liked_pid = None
                for p in playlists.get('playlist', []):
                    if p.get('specialType') == 5:
                        liked_pid = p['id']
                        break
                if liked_pid:
                    info = playlist_detail(liked_pid, cookies)
                    raw_tracks = info.get('tracks', [])
                else:
                    raw_tracks = []
            except Exception as e:
                api_service.logger.warning(f"获取喜欢列表失败: {e}")
                raw_tracks = []

            tracks = _build_recommend_tracks(
                raw_tracks, source_type, '我喜欢的音乐',
                local_tracks=None,
            )
            tracks = _sort_tracks_by_preference(tracks, sort_order)
            total = len(tracks)
            total_pages = max(1, (total + page_size - 1) // page_size)
            paged = tracks[(page - 1) * page_size : page * page_size]
            return APIResponse.success({
                'total': total, 'page': page, 'page_size': page_size,
                'total_pages': total_pages,
                'source_type': source_type,
                'source_label': '我喜欢的音乐',
                'generated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                'tracks': [t.model_dump() for t in paged],
            }, "ok")
        cookies = _pb_load_cookies()
        raw_tracks = []
        playlist_name = ''

        if cookies:
            pid = int(playlist_id) if playlist_id else _NETEASE_HOT_CHART_ID
            try:
                playlist_info = netease_playlist_detail(pid, cookies)
                raw_tracks = playlist_info.get('tracks', [])
                playlist_name = playlist_info.get('name', '网易云热榜' if source_type == 'hot_list' else '')
            except Exception as e:
                api_service.logger.warning(f"网易云 API 调用失败: {e}")
                raw_tracks = []
                playlist_name = ''
        else:
            api_service.logger.info("无有效网易云 Cookie")

        tracks = _build_recommend_tracks(
            raw_tracks, source_type,
            playlist_name or '网易云热榜',
            local_tracks=None,
        )
        tracks = _sort_tracks_by_preference(tracks, sort_order)

        # ── 分页 ──
        total = len(tracks)
        total_pages = max(1, (total + page_size - 1) // page_size)
        paged = tracks[(page - 1) * page_size : page * page_size]

        # ── 后台预下载（全量，非仅分页） ──
        netease_unmatched = [t for t in tracks if t.source == 'netease' and t.bpm < 0]
        if netease_unmatched:
            _async_download_and_score(netease_unmatched, cookies, username)

        return APIResponse.success({
            'total': total, 'page': page, 'page_size': page_size,
            'total_pages': total_pages,
            'source_type': source_type,
            'source_label': playlist_name or '网易云热榜',
            'generated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'tracks': [t.model_dump() for t in paged],
        }, "ok")
    except Exception as e:
        api_service.logger.error(f"推荐接口异常: {e}")
        return APIResponse.error(str(e), 500)


# ────────────────────────── v3 喜欢/取消喜欢 ──────────────────────────


@app.route('/api/v3/music/liked-ids', methods=['GET'])
def api_v3_music_liked_ids():
    """获取当前用户所有已喜欢歌曲 ID 列表（带内存缓存）"""
    global _liked_ids_cache, _liked_ids_cookie_hash
    try:
        cookies = _pb_load_cookies()
        if not cookies:
            return APIResponse.error("需要配置网易云 Cookie", 400)
        cookie_hash = hash(frozenset(str(v)[:20] for v in cookies.values()))
        if _liked_ids_cache is not None and _liked_ids_cookie_hash == cookie_hash:
            return APIResponse.success({'ids': _liked_ids_cache, 'total': len(_liked_ids_cache)})

        liked_pid = _get_liked_pid()
        if not liked_pid:
            return APIResponse.success({'ids': _liked_ids_cache or [], 'total': len(_liked_ids_cache or [])})

        import requests as _r
        url = f"https://music.163.com/api/v6/playlist/detail?id={liked_pid}"
        hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://music.163.com/'}
        resp = _r.get(url, headers=hdrs, cookies=cookies, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if body.get('code') != 200:
            return APIResponse.error(body.get('message', '获取歌单失败'), 502)
        playlist = body.get('playlist', {})
        ids = [t['id'] for t in playlist.get('trackIds', [])]
        _liked_ids_cache = ids
        _liked_ids_cookie_hash = cookie_hash
        api_service.logger.info(f"liked-ids 缓存刷新: {len(ids)} 首")
        return APIResponse.success({'ids': ids, 'total': len(ids)})
    except Exception as e:
        api_service.logger.error(f"获取 liked-ids 失败: {e}")
        return APIResponse.error(str(e), 502)


_liked_pid_cache = None  # 喜欢歌单 ID 缓存


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


@app.route('/api/v3/music/like', methods=['POST'])
def api_v3_music_like():
    """红心/取消红心 — 通过 playlist/manipulate/tracks 操作喜欢歌单"""
    global _liked_ids_cache
    try:
        data = request.get_json(force=True)
        if not data:
            return APIResponse.error("请求体不能为空", 400)
        track_id = data.get('track_id')
        like = data.get('like')
        if not track_id or not isinstance(track_id, int) or track_id <= 0:
            return APIResponse.error("track_id 必须为正整数", 400)
        if not isinstance(like, bool):
            return APIResponse.error("like 必须为布尔值", 400)

        cookies = _pb_load_cookies()
        if not cookies:
            return APIResponse.error("需要配置网易云 Cookie", 400)
        csrf = cookies.get('__csrf', '')
        if not csrf:
            return APIResponse.error("Cookie 中缺少 __csrf", 400)

        liked_pid = _get_liked_pid()
        if not liked_pid:
            return APIResponse.error("未找到喜欢歌单 (specialType=5)", 400)

        op = 'add' if like else 'del'
        url = f'https://music.163.com/api/playlist/manipulate/tracks?csrf_token={csrf}'
        form = {'op': op, 'pid': str(liked_pid), 'trackIds': f'[{track_id}]'}
        hdrs = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://music.163.com/',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        import requests as _r
        resp = _r.post(url, headers=hdrs, cookies=cookies, data=form, timeout=15)
        body = resp.json()
        if body.get('code') == 200:
            # 更新缓存
            if _liked_ids_cache is not None:
                if like and track_id not in _liked_ids_cache:
                    _liked_ids_cache.append(track_id)
                elif not like:
                    try:
                        _liked_ids_cache.remove(track_id)
                    except ValueError:
                        pass
            api_service.logger.info(f"like 操作成功: track={track_id} op={op}")
            return APIResponse.success({'track_id': track_id, 'liked': like})
        else:
            return APIResponse.error(body.get('message', '操作失败'), 502)
    except Exception as e:
        api_service.logger.error(f"like操作失败: {e}")
        return APIResponse.error(str(e), 502)


@app.route('/api/v3/music/liked/songs', methods=['GET'])
def api_v3_music_liked_songs():
    """搜索/获取喜欢歌曲完整信息（含歌名/歌手/专辑/封面）

    Query params:
        keyword: 搜索关键词（为空则返回全部）
        offset:  偏移量，默认 0
        limit:   返回数量，默认 200
    """
    global _liked_songs_cache, _liked_songs_cookie_hash
    try:
        keyword = request.args.get('keyword', '').strip()
        offset = int(request.args.get('offset', 0))
        limit = min(int(request.args.get('limit', 200)), 1000)

        cookies = _pb_load_cookies()
        if not cookies:
            return APIResponse.error("需要配置网易云 Cookie", 400)

        cookie_hash = hash(frozenset(str(v)[:20] for v in cookies.values()))
        if _liked_songs_cache is not None and _liked_songs_cookie_hash == cookie_hash:
            songs = _liked_songs_cache
        else:
            liked_pid = _get_liked_pid()
            if not liked_pid:
                return APIResponse.error("未找到喜欢歌单", 400)

            import requests as _r
            data = {'id': liked_pid, 'n': 100000, 's': 0}
            hdrs = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://music.163.com/',
            }
            resp = _r.post('https://music.163.com/api/v6/playlist/detail',
                           data=data, headers=hdrs, cookies=cookies, timeout=60)
            resp.raise_for_status()
            body = resp.json()
            if body.get('code') != 200:
                return APIResponse.error(body.get('message', '获取歌单详情失败'), 502)
            tracks = body.get('playlist', {}).get('tracks', [])
            songs = []
            for t in tracks:
                songs.append({
                    'id': t['id'],
                    'name': t['name'],
                    'artists': '/'.join(a.get('name', '') or '' for a in t.get('ar', []) if a.get('name')),
                    'album': t.get('al', {}).get('name', '') or '',
                    'picUrl': t.get('al', {}).get('picUrl', '') or '',
                })
            _liked_songs_cache = songs
            _liked_songs_cookie_hash = cookie_hash
            api_service.logger.info(f"liked-songs 缓存刷新: {len(songs)} 首")

        # 搜索过滤
        if keyword:
            kw = keyword.lower()
            songs = [s for s in songs if kw in s['name'].lower() or kw in s['artists'].lower()]

        total = len(songs)
        paged = songs[offset:offset + limit]

        # 同步更新 ID 缓存
        _liked_ids_cache = [s['id'] for s in songs]
        _liked_ids_cookie_hash = cookie_hash

        return APIResponse.success({'total': total, 'songs': paged})
    except Exception as e:
        api_service.logger.error(f"获取 liked-songs 失败: {e}")
        return APIResponse.error(str(e), 502)

# 加载.env文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env文件不是必须的

# 加载 config/settings.json（优先级最高）
def load_settings_json() -> Dict[str, Any]:
    """从 config/settings.json 加载项目配置"""
    settings_path = _PROJECT_ROOT / 'config' / 'settings.json'
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
config.download_lyric_save_lrc = settings.get('download_lyric_save_lrc', True)

start_api_server()

