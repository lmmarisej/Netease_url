"""
v3 API 路由：推荐排序、权重配置、播放历史、喜欢管理
"""

import sqlite3
import traceback
from datetime import datetime, timezone

from flask import request

from backend.api_core import APIResponse
from backend.recommendation_engine import get_recommendation_engine, FEATURE_KEYS, SLOT_HOUR_RANGES
from backend.auth import get_current_user


def register_v3_routes(app, api_service, _PROJECT_ROOT):
    """注册 v3 API 路由"""

    # ── 权重配置 ──
    @app.route('/api/v3/config/weights', methods=['GET', 'POST'])
    def api_v3_weights():
        engine = get_recommendation_engine()
        if request.method == 'GET':
            try:
                cfg = engine.get_config()
                return APIResponse.success(cfg, "ok")
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
        try:
            engine = get_recommendation_engine()
            info = engine.get_current_slot_info()
            return APIResponse.success(info, "ok")
        except Exception as e:
            return APIResponse.error(str(e), 500)

    @app.route('/api/v3/recommend/rank', methods=['POST'])
    def v3_recommend_rank():
        try:
            data = api_service._safe_get_request_data()
            tracks_input = data.get('tracks', [])
            if not tracks_input or not isinstance(tracks_input, list):
                return APIResponse.error("请提供 'tracks' 列表", 400)

            engine = get_recommendation_engine()
            hour = data.get('hour')
            slot = data.get('slot')
            if hour is not None:
                hour = int(hour)
            if slot and slot not in SLOT_HOUR_RANGES:
                return APIResponse.error(f"无效时段 '{slot}'", 400)

            ranked = engine.rank_tracks_to_dict(tracks_input, hour=hour, slot=slot)
            return APIResponse.success({
                'ranked': ranked, 'total': len(ranked),
                'applied_slot': ranked[0]['applied_slot'] if ranked else None,
                'slot_label': ranked[0]['slot_label'] if ranked else None,
            }, "推荐排序完成")
        except ValueError as e:
            return APIResponse.error(str(e), 400)
        except Exception as e:
            return APIResponse.error(f"排序失败: {str(e)}", 500)

    @app.route('/api/v3/recommend/rank-radar', methods=['POST'])
    def v3_recommend_rank_radar():
        try:
            data = api_service._safe_get_request_data()
            tracks_input = data.get('tracks', [])
            if not tracks_input or not isinstance(tracks_input, list):
                return APIResponse.error("请提供 'tracks' 列表", 400)

            engine = get_recommendation_engine()
            converted = []
            for t in tracks_input:
                radar = t.get('radar', [])
                if len(radar) != len(FEATURE_KEYS):
                    return APIResponse.error(f"雷达数组长度应为 {len(FEATURE_KEYS)}", 400)
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
                'ranked': ranked, 'total': len(ranked),
                'applied_slot': ranked[0]['applied_slot'] if ranked else None,
                'slot_label': ranked[0]['slot_label'] if ranked else None,
            }, "雷达排序完成")
        except ValueError as e:
            return APIResponse.error(str(e), 400)
        except Exception as e:
            return APIResponse.error(f"排序失败: {str(e)}", 500)

    # ── 播放日志 ──
    @app.route('/api/v3/music/log', methods=['POST'])
    def api_v3_music_log():
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
                    'is_skipped': is_skipped, 'skip_ratio': round(skip_ratio, 3),
                }, "已记录")
            finally:
                conn.close()
        except Exception as e:
            return APIResponse.error(str(e), 500)

    @app.route('/api/v3/music/history', methods=['GET'])
    def api_v3_music_history():
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
                items = [{
                    'id': r['id'], 'track_id': r['track_id'],
                    'title': r['title'], 'artist': r['artist'],
                    'play_duration': r['play_duration'], 'total_duration': r['total_duration'],
                    'is_skipped': bool(r['is_skipped']), 'timestamp': r['timestamp'],
                } for r in rows]
                return APIResponse.success({
                    'total': total, 'page': page, 'page_size': page_size, 'items': items,
                }, "ok")
            finally:
                conn.close()
        except Exception as e:
            return APIResponse.error(str(e), 500)

    # ── 推荐流 ──
    @app.route('/api/v3/music/recommend', methods=['GET'])
    def api_v3_music_recommend():
        try:
            from backend.playback_api import (
                _load_netease_cookies, _get_local_top_tracks,
                _build_recommend_tracks, _sort_tracks_by_preference,
                _async_download_and_score,
            )
            from backend.music_api import playlist_detail as netease_playlist_detail
            from backend.main import _NETEASE_HOT_CHART_ID

            source_type = request.args.get('source_type', 'hot_list')
            playlist_id = request.args.get('playlist_id', None)
            sort_order = request.args.get('sort_order', 'desc')
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('page_size', 50, type=int)

            if source_type not in ('hot_list', 'custom_playlist', 'local_library', 'liked'):
                return APIResponse.error("source_type 仅支持 hot_list/custom_playlist/local_library/liked", 400)
            if source_type == 'custom_playlist' and not playlist_id:
                return APIResponse.error("custom_playlist 必须提供 playlist_id", 400)
            if sort_order not in ('asc', 'desc'):
                sort_order = 'desc'
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 200:
                page_size = 50

            username = get_current_user() or 'admin'

            if source_type == 'local_library':
                local_tracks = _get_local_top_tracks(username, limit=50)
                tracks = _build_recommend_tracks([], source_type, '本地音乐库', local_tracks=local_tracks)
                tracks = _sort_tracks_by_preference(tracks, sort_order)
                total = len(tracks)
                total_pages = max(1, (total + page_size - 1) // page_size)
                paged = tracks[(page - 1) * page_size: page * page_size]
                return APIResponse.success({
                    'total': total, 'page': page, 'page_size': page_size,
                    'total_pages': total_pages,
                    'source_type': source_type, 'source_label': '本地音乐库',
                    'tracks': [t.model_dump() for t in paged],
                }, "ok")

            if source_type == 'liked':
                cookies = _load_netease_cookies()
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

                tracks = _build_recommend_tracks(raw_tracks, source_type, '我喜欢的音乐', local_tracks=None)
                tracks = _sort_tracks_by_preference(tracks, sort_order)
                total = len(tracks)
                total_pages = max(1, (total + page_size - 1) // page_size)
                paged = tracks[(page - 1) * page_size: page * page_size]
                return APIResponse.success({
                    'total': total, 'page': page, 'page_size': page_size,
                    'total_pages': total_pages, 'source_type': source_type,
                    'source_label': '我喜欢的音乐',
                    'tracks': [t.model_dump() for t in paged],
                }, "ok")

            cookies = _load_netease_cookies()
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

            tracks = _build_recommend_tracks(raw_tracks, source_type,
                                             playlist_name or '网易云热榜', local_tracks=None)
            tracks = _sort_tracks_by_preference(tracks, sort_order)

            total = len(tracks)
            total_pages = max(1, (total + page_size - 1) // page_size)
            paged = tracks[(page - 1) * page_size: page * page_size]

            netease_unmatched = [t for t in tracks if t.source == 'netease' and t.bpm < 0]
            if netease_unmatched:
                _async_download_and_score(netease_unmatched, cookies, username)

            return APIResponse.success({
                'total': total, 'page': page, 'page_size': page_size,
                'total_pages': total_pages, 'source_type': source_type,
                'source_label': playlist_name or '网易云热榜',
                'tracks': [t.model_dump() for t in paged],
            }, "ok")
        except Exception as e:
            api_service.logger.error(f"推荐接口异常: {e}")
            return APIResponse.error(str(e), 500)

    # ── 喜欢/取消喜欢 ──
    @app.route('/api/v3/music/liked-ids', methods=['GET'])
    def api_v3_music_liked_ids():
        import requests as _r
        from backend.playback_api import _load_netease_cookies
        from backend.main import _liked_ids_cache, _liked_ids_cookie_hash, _get_liked_pid

        try:
            cookies = _load_netease_cookies()
            if not cookies:
                return APIResponse.error("需要配置网易云 Cookie", 400)
            cookie_hash = hash(frozenset(str(v)[:20] for v in cookies.values()))
            if _liked_ids_cache is not None and _liked_ids_cookie_hash == cookie_hash:
                return APIResponse.success({'ids': _liked_ids_cache, 'total': len(_liked_ids_cache)})

            liked_pid = _get_liked_pid()
            if not liked_pid:
                return APIResponse.success({'ids': _liked_ids_cache or [], 'total': len(_liked_ids_cache or [])})

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
            return APIResponse.success({'ids': ids, 'total': len(ids)})
        except Exception as e:
            return APIResponse.error(str(e), 502)

    @app.route('/api/v3/music/like', methods=['POST'])
    def api_v3_music_like():
        import requests as _r
        from backend.playback_api import _load_netease_cookies
        from backend.main import _liked_ids_cache, _get_liked_pid

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

            cookies = _load_netease_cookies()
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
            resp = _r.post(url, headers=hdrs, cookies=cookies, data=form, timeout=15)
            body = resp.json()
            if body.get('code') == 200:
                if _liked_ids_cache is not None:
                    if like and track_id not in _liked_ids_cache:
                        _liked_ids_cache.append(track_id)
                    elif not like:
                        try:
                            _liked_ids_cache.remove(track_id)
                        except ValueError:
                            pass
                return APIResponse.success({'track_id': track_id, 'liked': like})
            return APIResponse.error(body.get('message', '操作失败'), 502)
        except Exception as e:
            return APIResponse.error(str(e), 502)

    @app.route('/api/v3/music/liked/songs', methods=['GET'])
    def api_v3_music_liked_songs():
        import requests as _r
        from backend.playback_api import _load_netease_cookies
        from backend.main import (_liked_songs_cache, _liked_songs_cookie_hash,
                                   _liked_ids_cache, _liked_ids_cookie_hash, _get_liked_pid)

        try:
            keyword = request.args.get('keyword', '').strip()
            offset = int(request.args.get('offset', 0))
            limit = min(int(request.args.get('limit', 200)), 1000)

            cookies = _load_netease_cookies()
            if not cookies:
                return APIResponse.error("需要配置网易云 Cookie", 400)

            cookie_hash = hash(frozenset(str(v)[:20] for v in cookies.values()))
            if _liked_songs_cache is not None and _liked_songs_cookie_hash == cookie_hash:
                songs = _liked_songs_cache
            else:
                liked_pid = _get_liked_pid()
                if not liked_pid:
                    return APIResponse.error("未找到喜欢歌单", 400)

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
                songs = [{
                    'id': t['id'], 'name': t['name'],
                    'artists': '/'.join(a.get('name', '') or '' for a in t.get('ar', []) if a.get('name')),
                    'album': t.get('al', {}).get('name', '') or '',
                    'picUrl': t.get('al', {}).get('picUrl', '') or '',
                } for t in tracks]
                _liked_songs_cache = songs
                _liked_songs_cookie_hash = cookie_hash

            if keyword:
                kw = keyword.lower()
                songs = [s for s in songs if kw in s['name'].lower() or kw in s['artists'].lower()]

            total = len(songs)
            paged = songs[offset:offset + limit]

            _liked_ids_cache = [s['id'] for s in songs]
            _liked_ids_cookie_hash = cookie_hash

            return APIResponse.success({'total': total, 'songs': paged})
        except Exception as e:
            return APIResponse.error(str(e), 502)
