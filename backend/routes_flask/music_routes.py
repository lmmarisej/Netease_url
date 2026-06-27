"""
音乐相关路由：歌曲信息、搜索、歌单、专辑

register_music_routes(app, api_service, config, operation_logger, _PROJECT_ROOT)
"""

import traceback
from pathlib import Path

from flask import request

from backend.api_core import APIResponse
from backend.music_api import (
    url_v1, name_v1, lyric_v1,
    search_music, playlist_detail, album_detail,
    APIException,
)
from backend.qq_music_api import qq_search_music
from backend.event_bus import EventType, fire_event
from backend.auth import get_current_user
from backend.lyrics_db import LyricsDB


def register_music_routes(app, api_service, config, operation_logger, _PROJECT_ROOT):
    """注册音乐相关路由"""

    @app.route('/api/song', methods=['GET', 'POST'])
    @app.route('/api/Song_V1', methods=['GET', 'POST'])
    def get_song_info():
        try:
            data = api_service._safe_get_request_data()
            song_ids = data.get('ids') or data.get('id')
            url = data.get('url')
            level = data.get('level', 'lossless')
            info_type = data.get('type', 'url')

            if not song_ids and not url:
                return APIResponse.error("必须提供 'ids'、'id' 或 'url' 参数")

            music_id = api_service._extract_music_id(song_ids or url)

            valid_levels = ['standard', 'exhigh', 'lossless', 'hires', 'sky', 'jyeffect', 'jymaster']
            if level not in valid_levels:
                return APIResponse.error(f"无效的音质参数，支持: {', '.join(valid_levels)}")

            valid_types = ['url', 'name', 'lyric', 'json']
            if info_type not in valid_types:
                return APIResponse.error(f"无效的类型参数，支持: {', '.join(valid_types)}")

            cookies = api_service._get_cookies()

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
                    'music_id': music_id, 'info_type': 'name',
                }, source='api')
                return APIResponse.success(result, "获取歌曲信息成功")

            elif info_type == 'lyric':
                result = lyric_v1(music_id, cookies)
                return APIResponse.success(result, "获取歌词成功")

            elif info_type == 'json':
                song_info = name_v1(music_id)
                url_info = url_v1(music_id, level, cookies)
                lyric_info = lyric_v1(music_id, cookies)

                if not song_info or 'songs' not in song_info or not song_info['songs']:
                    return APIResponse.error("未找到歌曲信息", 404)

                song_data = song_info['songs'][0]

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

                if url_info and url_info.get('data') and len(url_info['data']) > 0:
                    url_data = url_info['data'][0]
                    response_data.update({
                        'url': url_data.get('url', ''),
                        'size': api_service._format_file_size(url_data.get('size', 0)),
                        'level': url_data.get('level', level)
                    })
                else:
                    response_data.update({'url': '', 'size': '获取失败'})

                fire_event(EventType.SONG_INFO_FETCHED, {
                    'music_id': music_id, 'info_type': 'json',
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
    def search_music_api():
        try:
            data = api_service._safe_get_request_data()
            keyword = data.get('keyword') or data.get('keywords') or data.get('q')
            limit = int(data.get('limit', 30))
            source = (data.get('source') or 'netease').strip().lower()

            validation_error = api_service._validate_request_params({'keyword': keyword})
            if validation_error:
                return validation_error

            if limit > 100:
                limit = 100

            if source == 'qq':
                from backend.main import _read_qq_cookie
                result = qq_search_music(keyword, limit, cookie=_read_qq_cookie())
            else:
                source = 'netease'
                cookies = api_service._get_cookies()
                result = search_music(keyword, cookies, limit)

            if result:
                for song in result:
                    song.setdefault('source', source)
                    if 'artists' in song:
                        song['artist_string'] = song['artists']

            fire_event(EventType.SEARCH_PERFORMED, {
                'keyword': keyword, 'source': source,
                'result_count': len(result) if result else 0,
            }, source='api')
            return APIResponse.success(result, "搜索完成")
        except ValueError as e:
            return APIResponse.error(f"参数格式错误: {str(e)}")
        except Exception as e:
            api_service.logger.error(f"搜索音乐异常: {e}\n{traceback.format_exc()}")
            return APIResponse.error(f"搜索失败: {str(e)}", 500)

    @app.route('/api/playlist', methods=['GET', 'POST'])
    def get_playlist():
        try:
            data = api_service._safe_get_request_data()
            playlist_id = data.get('id')

            validation_error = api_service._validate_request_params({'playlist_id': playlist_id})
            if validation_error:
                return validation_error

            cookies = api_service._get_cookies()
            result = playlist_detail(playlist_id, cookies)

            response_data = {'status': 'success', 'playlist': result}
            playlist_name = result.get('name', '未知歌单') if result else '未知歌单'
            operation_logger.info(f"[歌单解析] ID={playlist_id} 名称={playlist_name}")
            fire_event(EventType.PLAYLIST_FETCHED, {
                'playlist_id': playlist_id, 'playlist_name': playlist_name,
                'track_count': len(result.get('tracks', [])) if result else 0,
            }, source='api')
            return APIResponse.success(response_data, "获取歌单详情成功")
        except Exception as e:
            api_service.logger.error(f"获取歌单异常: {e}\n{traceback.format_exc()}")
            return APIResponse.error(f"获取歌单失败: {str(e)}", 500)

    @app.route('/api/album', methods=['GET', 'POST'])
    def get_album():
        try:
            data = api_service._safe_get_request_data()
            album_id = data.get('id')

            validation_error = api_service._validate_request_params({'album_id': album_id})
            if validation_error:
                return validation_error

            cookies = api_service._get_cookies()
            result = album_detail(album_id, cookies)

            response_data = {'status': 200, 'album': result}
            fire_event(EventType.ALBUM_FETCHED, {
                'album_id': album_id,
                'album_name': result.get('name', '') if result else '',
            }, source='api')
            return APIResponse.success(response_data, "获取专辑详情成功")
        except Exception as e:
            api_service.logger.error(f"获取专辑异常: {e}\n{traceback.format_exc()}")
            fire_event(EventType.API_ERROR, {'endpoint': '/album', 'error': str(e)}, source='api')
            return APIResponse.error(f"获取专辑失败: {str(e)}", 500)
