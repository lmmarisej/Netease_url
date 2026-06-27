"""
系统路由：健康检查、日志、任务、API信息、API文档、流媒体代理、前端SPA
"""

import os
import sys
import time
import traceback
import requests

from pathlib import Path
from flask import request, Response, stream_with_context, send_from_directory

from backend.api_core import APIResponse
from backend.task_manager import task_manager, TaskStatus
from backend.event_bus import EventType
from backend.auth import get_current_user, set_current_user, verify_token
from backend.music_api import url_v1


AUTH_WHITELIST = {
    '/api/auth/login', '/api/auth/register', '/api/auth/verify',
    '/api/health', '/api/info', '/api/lyrics',
}


def _extract_token_from_request():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    token = request.args.get('token', '')
    if token:
        return token
    return None


def register_system_routes(app, api_service, config, _PROJECT_ROOT):
    """注册系统路由（health/logs/tasks/info/api-docs/frontend/streaming）"""
    FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')

    # ── 请求前/后处理 ──
    @app.before_request
    def before_request():
        api_service.logger.info(
            f"{request.method} {request.path} - IP: {request.remote_addr}"
        )
        if request.method == 'OPTIONS':
            return '', 200
        if not request.path.startswith('/api/'):
            return
        if request.path in AUTH_WHITELIST:
            return
        if request.path.startswith('/api/v3/'):
            token = _extract_token_from_request()
            if token:
                username = verify_token(token)
                if username:
                    set_current_user(username)
            return
        token = _extract_token_from_request()
        if not token:
            return APIResponse.error("未提供认证Token，请先登录", 401)
        username = verify_token(token)
        if not username:
            return APIResponse.error("Token无效或已过期，请重新登录", 401)
        set_current_user(username)

    @app.after_request
    def after_request(response: Response) -> Response:
        response.headers.add('Access-Control-Allow-Origin', config.cors_origins)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        response.headers.add('Access-Control-Max-Age', '3600')
        return response

    @app.errorhandler(400)
    def handle_bad_request(e):
        return APIResponse.error("请求参数错误", 400)

    @app.errorhandler(404)
    def handle_not_found(e):
        return APIResponse.error("请求的资源不存在", 404)

    @app.errorhandler(500)
    def handle_internal_error(e):
        api_service.logger.error(f"服务器内部错误: {e}")
        return APIResponse.error("服务器内部错误", 500)

    # ── 健康检查 ──
    @app.route('/api/health', methods=['GET'])
    def health_check():
        try:
            cookie_status = api_service.cookie_manager.is_cookie_valid()
            return APIResponse.success({
                'service': 'running',
                'timestamp': int(time.time()),
                'cookie_status': 'valid' if cookie_status else 'invalid',
                'downloads_dir': str(api_service.downloads_path.absolute()),
                'version': '2.0.0',
            }, "API服务运行正常")
        except Exception as e:
            return APIResponse.error(f"健康检查失败: {str(e)}", 500)

    # ── API 信息 ──
    @app.route('/api/info', methods=['GET'])
    def api_info():
        try:
            return APIResponse.success({
                'name': '网易云音乐API服务', 'version': '2.0.0',
                'endpoints': {
                    '/health': 'GET - 健康检查',
                    '/song': 'GET/POST - 获取歌曲信息',
                    '/search': 'GET/POST - 搜索音乐',
                    '/playlist': 'GET/POST - 获取歌单详情',
                    '/album': 'GET/POST - 获取专辑详情',
                    '/download': 'GET/POST - 下载音乐',
                },
                'supported_qualities': _NETEASE_QUALITY_ORDER,
                'config': {
                    'downloads_dir': str(api_service.downloads_path.absolute()),
                    'sync_enabled': config.enable_sync,
                }
            }, "API信息获取成功")
        except Exception as e:
            return APIResponse.error(f"获取API信息失败: {str(e)}", 500)

    # ── API 文档 ──
    @app.route('/api/api-docs', methods=['GET'])
    def api_docs_json():
        try:
            import json
            config_path = _PROJECT_ROOT / 'config' / 'api.json'
            if not config_path.exists():
                return APIResponse.error("API 配置文件不存在", 404)
            with open(config_path, 'r', encoding='utf-8') as f:
                api_config = json.load(f)
            return APIResponse.success(api_config, "API文档获取成功")
        except Exception as e:
            return APIResponse.error(f"获取API文档失败: {str(e)}", 500)

    # ── 日志 ──
    @app.route('/api/logs', methods=['GET'])
    def api_logs():
        try:
            logs_dir = _PROJECT_ROOT / 'logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_files = sorted([f.name for f in logs_dir.glob('*.log')], reverse=True)
            requested_file = request.args.get('file', '')
            if requested_file:
                log_path = logs_dir / requested_file
                if not log_path.exists():
                    return APIResponse.error(f"日志文件 {requested_file} 不存在", 404)
            else:
                if not log_files:
                    return APIResponse.success({
                        'files': [], 'current_file': '', 'lines': [], 'total_lines': 0,
                    }, "暂无日志文件")
                log_path = logs_dir / log_files[0]

            max_lines = int(request.args.get('limit', 1000))
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
            total_lines = len(all_lines)
            recent_lines = list(reversed(all_lines[-max_lines:]))
            return APIResponse.success({
                'files': log_files, 'current_file': log_path.name,
                'lines': [line.rstrip('\n\r') for line in recent_lines],
                'total_lines': total_lines,
            }, "日志获取成功")
        except Exception as e:
            return APIResponse.error(f"获取日志失败: {str(e)}", 500)

    @app.route('/api/logs/cleanup', methods=['POST'])
    def api_logs_cleanup():
        try:
            logs_dir = _PROJECT_ROOT / 'logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            cleaned = []
            for log_file in logs_dir.glob('*.log'):
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write('')
                cleaned.append(log_file.name)
            return APIResponse.success({'cleaned': cleaned}, f"已清空 {len(cleaned)} 个日志文件")
        except Exception as e:
            return APIResponse.error(f"清理日志失败: {str(e)}", 500)

    # ── 任务管理 ──
    @app.route('/api/tasks', methods=['GET'])
    def api_tasks_list():
        try:
            task_type = request.args.get('type', '')
            status = request.args.get('status', '')
            limit = int(request.args.get('limit', 50))
            tasks = task_manager.get_tasks(task_type=task_type or None,
                                           status=status or None, limit=limit)
            return APIResponse.success([task_manager.task_to_dict(t) for t in tasks], "任务列表获取成功")
        except Exception as e:
            return APIResponse.error(f"获取任务列表失败: {str(e)}", 500)

    @app.route('/api/tasks/<task_id>', methods=['GET'])
    def api_task_detail(task_id):
        task = task_manager.get_task(task_id)
        if not task:
            return APIResponse.error("任务不存在", 404)
        return APIResponse.success(task_manager.task_to_dict(task), "任务详情获取成功")

    @app.route('/api/tasks/<task_id>', methods=['DELETE'])
    def api_task_remove(task_id):
        if task_manager.remove_task(task_id):
            return APIResponse.success(None, "任务已删除")
        return APIResponse.error("任务不存在", 404)

    @app.route('/api/tasks/clear', methods=['POST'])
    def api_tasks_clear():
        count = task_manager.clear_completed()
        return APIResponse.success({'cleared': count}, f"已清理 {count} 个已完成任务")

    @app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
    def api_task_cancel(task_id):
        task = task_manager.get_task(task_id)
        if not task:
            return APIResponse.error("任务不存在", 404)
        if task.status != TaskStatus.RUNNING:
            return APIResponse.error("只能取消运行中的任务", 400)
        task_manager.update_task(task_id, status=TaskStatus.CANCELLED, message='用户取消')
        return APIResponse.success(None, "任务已取消")

    # ── 流媒体代理 ──
    @app.route('/api/v3/music/stream/<track_id>', methods=['GET', 'HEAD'])
    def api_v3_music_stream(track_id):
        try:
            from backend.playback_api import _load_netease_cookies
            cookies = _load_netease_cookies()
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

            file_size = 0
            try:
                hr = requests.head(song_url, headers=hdrs, timeout=15)
                file_size = int(hr.headers.get('Content-Length', 0))
            except Exception:
                pass

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

            if r.status_code == 206:
                r.raise_for_status()
                def _range():
                    sent = 0
                    for c in r.iter_content(chunk_size=65536):
                        if sent >= content_length:
                            break
                        yield c
                        sent += len(c)
                resp = Response(stream_with_context(_range()), status=206,
                                content_type=content_type)
            else:
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
                resp = Response(stream_with_context(_skip()), status=206,
                                content_type=content_type)

            resp.headers['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
            resp.headers['Content-Length'] = str(content_length)
            resp.headers['Accept-Ranges'] = 'bytes'
            return resp

        except Exception as e:
            api_service.logger.error(f"流媒体代理异常: {e}")
            return APIResponse.error(str(e), 500)

    # ── SPA 前端 ──
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path and path.startswith('api/'):
            return
        file_path = os.path.join(FRONTEND_DIR, path) if path else os.path.join(FRONTEND_DIR, 'index.html')
        if os.path.isfile(file_path):
            return send_from_directory(FRONTEND_DIR, path) if path else send_from_directory(FRONTEND_DIR, 'index.html')
        return send_from_directory(FRONTEND_DIR, 'index.html')


_NETEASE_QUALITY_ORDER = ['jymaster', 'sky', 'jyeffect', 'hires', 'lossless', 'exhigh', 'standard']
