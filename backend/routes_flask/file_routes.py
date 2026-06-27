"""
文件管理路由
"""

import os
import time
import sqlite3
import traceback
from pathlib import Path

from flask import request, send_file

from backend.api_core import APIResponse
from backend.auth import get_current_user


def register_file_routes(app, api_service, _PROJECT_ROOT):
    """注册文件管理路由"""

    @app.route('/api/files/list', methods=['GET'])
    def api_files_list():
        try:
            from backend.main import _get_user_downloads_path
            downloads_dir = _get_user_downloads_path()
            files = []
            for f in sorted(downloads_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file():
                    stat = f.stat()
                    files.append({
                        'name': f.name, 'size': stat.st_size,
                        'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                    })
            return APIResponse.success({'files': files}, "文件列表获取成功")
        except Exception as e:
            return APIResponse.error(f"获取文件列表失败: {str(e)}", 500)

    @app.route('/api/files/delete', methods=['POST'])
    def api_files_delete():
        try:
            from backend.main import _get_user_downloads_path
            data = api_service._safe_get_request_data()
            filename = data.get('filename', '').strip()
            if not filename:
                return APIResponse.error("文件名不能为空", 400)
            file_path = _get_user_downloads_path() / filename
            if not file_path.resolve().is_relative_to(_get_user_downloads_path().resolve()):
                return APIResponse.error("非法文件路径", 403)
            if not file_path.exists():
                return APIResponse.error("文件不存在", 404)
            file_path.unlink()
            return APIResponse.success({'filename': filename}, "文件已删除")
        except Exception as e:
            return APIResponse.error(f"删除文件失败: {str(e)}", 500)

    @app.route('/api/files/stream/<path:filename>', methods=['GET'])
    def api_files_stream(filename):
        try:
            from backend.main import _get_user_downloads_path
            downloads_dir = _PROJECT_ROOT / 'downloads'
            downloads_root = downloads_dir.resolve()

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

            if file_path is None or not file_path.exists():
                try:
                    from services.song_storage import get_song_storage_service
                    storage = get_song_storage_service()
                    user = get_current_user() or 'admin'
                    search_name = Path(filename).name
                    songs = storage.get_user_songs(user)
                    found_hash = None
                    for s in songs:
                        orig = s.get('original_filename', '')
                        if orig == search_name or Path(orig).name == search_name:
                            found_hash = s['content_hash']
                            break
                    if not found_hash:
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

            if file_path is None or not file_path.exists():
                return APIResponse.error("文件不存在", 404)

            download = request.args.get('download', '0') == '1'
            ext = file_path.suffix.lower()
            mime_map = {'.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.m4a': 'audio/mp4',
                        '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.wma': 'audio/x-ms-wma'}
            mimetype = mime_map.get(ext, 'application/octet-stream')

            response = send_file(str(file_path), mimetype=mimetype, as_attachment=download)
            if not download:
                response.headers['Accept-Ranges'] = 'bytes'
            return response
        except Exception as e:
            return APIResponse.error(f"文件传输失败: {str(e)}", 500)

    @app.route('/api/files/read/<path:filename>', methods=['GET'])
    def api_files_read(filename):
        try:
            from backend.main import _get_user_downloads_path
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
        try:
            from backend.main import _get_user_downloads_path
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
            return APIResponse.success({'filename': filename}, "文件保存成功")
        except Exception as e:
            return APIResponse.error(f"保存文件失败: {str(e)}", 500)
