"""
歌词相关路由：公开查询(SQLite+代理)、CRUD、高级查询
"""

import re
import json as _json
import traceback
from pathlib import Path

from flask import request, Response

from backend.api_core import APIResponse
from backend.music_api import search_music, lyric_v1, name_v1, APIException
from backend.lyrics_db import LyricsDB, save_lrc_file
from backend.event_bus import EventType, fire_event
from backend.auth import get_current_user, set_current_user, verify_token


def _get_lyrics_db():
    db = LyricsDB()
    db.set_user(get_current_user() or '')
    return db


def _fix_ts(text):
    if not text:
        return ''
    return re.sub(r'(\[\d{2}:\d{2}\.\d{2})\d\]', r'\1]', text)


def register_lyrics_routes(app, api_service, config, _PROJECT_ROOT):
    """注册歌词相关路由"""

    # ── 公开歌词查询（无需鉴权）──
    @app.route('/api/lyrics', methods=['GET'])
    def public_lyrics_query():
        lrc = ''
        try:
            title = request.args.get('title', '').strip()
            artist = request.args.get('artist', '').strip()

            if not title:
                return Response('', mimetype='text/plain; charset=utf-8')

            db = LyricsDB()
            result = db.search_public(title=title, artist=artist)
            if result:
                lrc = result.get('original_lyric', '')
                return Response(_fix_ts(lrc), mimetype='text/plain; charset=utf-8')

            # 代理网易云搜索
            search_keyword = f"{title} {artist}".strip()
            from backend.main import _extract_token_from_request, _get_user_cookie_path, _get_user_downloads_path
            token = _extract_token_from_request()
            if token:
                username = verify_token(token)
                if username:
                    set_current_user(username)
            api_service.cookie_manager.set_cookie_file(_get_user_cookie_path())
            cookies = api_service.cookie_manager.parse_cookies()
            if not cookies:
                return Response('', mimetype='text/plain; charset=utf-8')

            search_results = search_music(search_keyword, cookies, limit=5)
            if not search_results:
                return Response('', mimetype='text/plain; charset=utf-8')

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

            db.save_lyric(
                song_id=song_id, song_name=song_name, artist=song_artist,
                album='', original_lyric=lrc, translated_lyric=tlrc,
                lyric_raw=_json.dumps(lyric_result, ensure_ascii=False),
            )
            if config.download_lyric_save_lrc:
                safe_stem = ''.join(c for c in f"{song_artist} - {song_name}" if c not in r'<>:"/\|?*')
                save_lrc_file(_get_user_downloads_path(), safe_stem, lrc, tlrc)

            api_service.logger.info(f"公开歌词查询代理成功: {title} → song_id={song_id}")

        except Exception as e:
            api_service.logger.error(f"公开歌词查询异常: {e}")

        return Response(_fix_ts(lrc), mimetype='text/plain; charset=utf-8')

    # ── 歌词管理 CRUD ──
    @app.route('/api/lyrics/list', methods=['GET'])
    def get_lyrics_list():
        try:
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
            db = _get_lyrics_db()
            items, total = db.get_all_lyrics(limit=limit, offset=offset)
            return APIResponse.success({'items': items, 'total': total,
                                        'limit': limit, 'offset': offset}, "获取歌词列表成功")
        except Exception as e:
            return APIResponse.error(f"获取歌词列表失败: {str(e)}", 500)

    @app.route('/api/lyrics/search', methods=['GET'])
    def search_lyrics_api():
        try:
            keyword = request.args.get('keyword', '')
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
            if not keyword:
                return APIResponse.error("请提供搜索关键词")
            db = _get_lyrics_db()
            items, total = db.search_lyrics(keyword, limit=limit, offset=offset)
            return APIResponse.success({'items': items, 'total': total,
                                        'keyword': keyword}, "搜索歌词成功")
        except Exception as e:
            return APIResponse.error(f"搜索歌词失败: {str(e)}", 500)

    @app.route('/api/lyrics/<int:song_id>', methods=['GET'])
    def get_lyric_by_id(song_id):
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
        try:
            db = _get_lyrics_db()
            db.delete_lyric(song_id)
            return APIResponse.success(None, f"歌词 {song_id} 已删除")
        except Exception as e:
            return APIResponse.error(f"删除歌词失败: {str(e)}", 500)

    @app.route('/api/lyrics/count', methods=['GET'])
    def get_lyrics_count():
        try:
            db = _get_lyrics_db()
            count = db.get_count()
            return APIResponse.success({'count': count}, "获取歌词总数成功")
        except Exception as e:
            return APIResponse.error(f"获取歌词总数失败: {str(e)}", 500)

    @app.route('/api/lyrics/query', methods=['GET', 'POST'])
    def query_lyrics_api():
        try:
            data = api_service._safe_get_request_data()
            song_id = data.get('id') or data.get('ids')
            keyword = data.get('keyword') or data.get('title') or data.get('name')
            artist = (data.get('artist') or '').strip()

            if not song_id and not keyword:
                return APIResponse.error("必须提供 'id' 或 'keyword' 参数")

            cookies = api_service._get_cookies()

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

            song_meta = name_v1(music_id)
            song_name, ar_name, al_name, pic = '', '', '', ''
            if song_meta and song_meta.get('songs'):
                sd = song_meta['songs'][0]
                song_name = sd.get('name', '')
                ar_name = ', '.join(a.get('name', '') for a in sd.get('ar', []))
                al_name = sd.get('al', {}).get('name', '')
                pic = sd.get('al', {}).get('picUrl', '')

            lyric_info = lyric_v1(music_id, cookies)
            lyric = lyric_info.get('lrc', {}).get('lyric', '') if lyric_info else ''
            tlyric = lyric_info.get('tlyric', {}).get('lyric', '') if lyric_info else ''

            if not lyric:
                return APIResponse.error("未找到该歌曲的歌词", 404)

            fire_event(EventType.SONG_INFO_FETCHED, {
                'music_id': music_id, 'info_type': 'lyric_query',
                'song_name': song_name, 'artist': ar_name,
            }, source='api')

            return APIResponse.success({
                'id': music_id, 'name': song_name, 'ar_name': ar_name,
                'al_name': al_name, 'pic': pic, 'lyric': lyric, 'tlyric': tlyric,
            }, "获取歌词成功")
        except APIException as e:
            return APIResponse.error(f"API调用失败: {str(e)}", 500)
        except Exception as e:
            return APIResponse.error(f"服务器错误: {str(e)}", 500)
