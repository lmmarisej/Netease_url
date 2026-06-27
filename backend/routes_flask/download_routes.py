"""
下载相关路由：网易云 + QQ音乐下载
"""

import traceback
import requests
from pathlib import Path
from urllib.parse import quote
from threading import Thread

from flask import request, Response, stream_with_context

from backend.api_core import APIResponse
from backend.music_api import url_v1, name_v1, lyric_v1, APIException
from backend.qq_music_api import QQMusicAPI, QQAPIException, map_quality_to_qq
from backend.task_manager import task_manager, TaskStatus
from backend.event_bus import EventType, fire_event
from backend.auth import get_current_user


_NETEASE_QUALITY_ORDER = ['jymaster', 'sky', 'jyeffect', 'hires', 'lossless', 'exhigh', 'standard']
_QUALITY_LABELS = {'standard': '标准', 'exhigh': '极高', 'lossless': '无损',
                   'hires': 'Hi-Res', 'sky': '环绕声', 'jyeffect': '高清环绕', 'jymaster': '母带'}
_QQ_QUALITY_LABELS = {'128': '标准', '320': '极高', 'flac': '无损', 'master': '母带'}


def _fetch_and_save_lyric(music_id, song_info, cookies, config, api_service, download_dir=''):
    """获取歌词并保存到 SQLite + 导出 .lrc 文件"""
    try:
        from backend.lyrics_db import LyricsDB, save_lrc_file
        import json as _json

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
        db.save_lyric(
            song_id=music_id, song_name=song_data.get('name', ''),
            artist=artist_name, album=album_name,
            original_lyric=original_lyric, translated_lyric=translated_lyric,
            lyric_raw=_json.dumps(lyric_result, ensure_ascii=False),
            username=username,
        )
        if config.download_lyric_save_lrc and download_dir:
            safe_stem = ''.join(c for c in f"{artist_name} - {song_data.get('name', '')}" if c not in r'<>:"/\|?*')
            if safe_stem:
                save_lrc_file(Path(download_dir), safe_stem, original_lyric, translated_lyric)
        api_service.logger.debug(f"歌词已保存: {music_id}")
    except Exception as e:
        api_service.logger.warning(f"保存歌词失败 (song_id={music_id}): {e}")


def _download_qq_music(songmid, quality, save_local, browser_download, download_dir,
                       config, api_service, operation_logger):
    """QQ音乐音源下载处理"""
    from backend.main import _read_qq_cookie
    qq_cookie = _read_qq_cookie()
    qq_api = QQMusicAPI(qq_cookie)
    task = task_manager.create_task('download', '下载中...', music_id=songmid, quality=quality)

    fire_event(EventType.DOWNLOAD_STARTED, {
        'music_id': songmid, 'quality': quality, 'source': 'qq',
        'task_id': task.task_id,
    }, source='api', async_mode=True)

    try:
        task_manager.update_task(task.task_id, status=TaskStatus.RUNNING,
                                 message='正在获取歌曲信息...', progress=10)
        detail = qq_api.get_song_detail(songmid)
        song_name = detail.get('name', 'unknown')
        artist_name = detail.get('artists', '')

        task_manager.update_task(task.task_id, message='正在获取下载链接...', progress=30)
        qq_quality = map_quality_to_qq(quality)
        url_info = qq_api.get_song_url(songmid, qq_quality)
        download_url = url_info.get('url')
        if not download_url:
            hint = '版权限制或无该音质' if qq_cookie else '需要在「Cookie 管理」中配置 QQ音乐登录 Cookie'
            task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                     message='无法获取下载链接', error=hint)
            return APIResponse.error(f"无法获取QQ音乐下载链接（{hint}）", 404)

        actual_quality = url_info.get('quality', qq_quality)
        file_ext = url_info.get('ext', '.mp3')

        task_manager.update_task(task.task_id, name=song_name, extra={
            'artist': artist_name, 'album': detail.get('album', ''),
            'quality': actual_quality, 'source': 'qq',
        })

        include_quality = getattr(config, 'download_quality_in_filename', True)
        base_name = f"{artist_name} - {song_name}"
        if include_quality:
            safe_name = f"{base_name} [QQ-{_QQ_QUALITY_LABELS.get(actual_quality, actual_quality)}]"
        else:
            safe_name = base_name
        safe_name = ''.join(c for c in safe_name if c not in r'<>:"/\|?*')
        filename = f"{safe_name}{file_ext}"

        qq_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://y.qq.com/',
        }

        # 模式3: 仅本地
        if save_local and not browser_download:
            file_path = download_dir / filename
            if file_path.exists():
                task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED,
                                         message='文件已存在', progress=100)
                operation_logger.info(f"[QQ下载] MID={songmid} 歌名={song_name} (已存在)")
            else:
                task_manager.update_task(task.task_id, message='正在后台下载...', progress=50)
                def _bg():
                    try:
                        r = requests.get(download_url, headers=qq_headers, stream=True, timeout=60)
                        r.raise_for_status()
                        with open(file_path, 'wb') as f:
                            for c in r.iter_content(chunk_size=8192):
                                f.write(c)
                        task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED,
                                                 message='下载完成', progress=100)
                    except Exception as e:
                        task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                                 message='下载失败', error=str(e))
                Thread(target=_bg, daemon=True).start()

            return APIResponse.success({
                'music_id': songmid, 'name': song_name, 'artist': artist_name,
                'quality': actual_quality, 'source': 'qq', 'filename': filename,
                'mode': 'local_only',
            }, "已开始后台保存到本地")

        # 模式1&2: 流式代理
        local_f = None
        if save_local:
            file_path = download_dir / filename
            local_f = open(file_path, 'wb')

        def stream_proxy():
            try:
                r = requests.get(download_url, headers=qq_headers, stream=True, timeout=60)
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=65536):
                    if local_f:
                        local_f.write(chunk)
                    yield chunk
                task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED,
                                         message='下载完成', progress=100)
            except Exception as e:
                task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                         message='下载失败', error=str(e))
            finally:
                if local_f:
                    local_f.close()

        mime_ext = file_ext.lstrip('.')
        resp = Response(stream_with_context(stream_proxy()), mimetype=f"audio/{mime_ext}")
        resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
        resp.headers['X-Download-Filename'] = quote(filename, safe='')
        return resp

    except QQAPIException as e:
        task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                 message='下载失败', error=str(e))
        return APIResponse.error(f"QQ音乐下载失败: {str(e)}", 502)
    except Exception as e:
        task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                 message='下载过程出错', error=str(e))
        return APIResponse.error(f"QQ音乐下载异常: {str(e)}", 500)


def register_download_routes(app, api_service, config, operation_logger, _PROJECT_ROOT):
    """注册下载相关路由"""

    @app.route('/api/download', methods=['GET', 'POST'])
    def download_music_api():
        try:
            data = api_service._safe_get_request_data()
            music_id = data.get('id')
            quality = data.get('quality', 'lossless')
            source = (data.get('source') or 'netease').strip().lower()

            save_local = config.download_save_local
            browser_download = config.download_browser
            from backend.main import _get_user_downloads_path
            download_dir = _get_user_downloads_path()

            validation_error = api_service._validate_request_params({'music_id': music_id})
            if validation_error:
                return validation_error

            valid_qualities = ['standard', 'exhigh', 'lossless', 'hires', 'sky', 'jyeffect', 'jymaster']
            if quality not in valid_qualities:
                return APIResponse.error(f"无效的音质参数，支持: {', '.join(valid_qualities)}")

            if source == 'qq':
                return _download_qq_music(str(music_id).strip(), quality, save_local,
                                          browser_download, download_dir,
                                          config, api_service, operation_logger)

            music_id = api_service._extract_music_id(music_id)
            cookies = api_service._get_cookies()

            task = task_manager.create_task('download', '下载中...', music_id=music_id, quality=quality)

            fire_event(EventType.DOWNLOAD_STARTED, {
                'music_id': music_id, 'quality': quality, 'task_id': task.task_id,
            }, source='api', async_mode=True)

            try:
                task_manager.update_task(task.task_id, status=TaskStatus.RUNNING,
                                         message='正在获取歌曲信息...', progress=10)
                song_info = name_v1(music_id)
                if not song_info or 'songs' not in song_info or not song_info['songs']:
                    task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                             message='未找到音乐信息', error='歌曲不存在')
                    return APIResponse.error("未找到音乐信息", 404)

                song_data_raw = song_info.get('songs', [{}])[0] if song_info.get('songs') else {}
                _fetch_and_save_lyric(music_id, song_info, cookies, config, api_service,
                                      str(download_dir))

                task_manager.update_task(task.task_id, message='正在获取下载链接...', progress=30)
                actual_quality = quality
                url_info = None

                try:
                    start_idx = _NETEASE_QUALITY_ORDER.index(quality)
                except ValueError:
                    start_idx = len(_NETEASE_QUALITY_ORDER) - 1

                for q in _NETEASE_QUALITY_ORDER[start_idx:]:
                    url_info = url_v1(music_id, q, cookies)
                    if url_info and url_info.get('data') and len(url_info['data']) > 0 and url_info['data'][0].get('url'):
                        actual_quality = q
                        if q != quality:
                            task_manager.update_task(task.task_id,
                                                     message=f'音质降级为 {q}', progress=35)
                        break
                    url_info = None

                if not url_info:
                    task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                             message='所有音质均不可用', error='版权限制或音质不支持')
                    return APIResponse.error("无法获取音乐下载链接", 404)

                song_data = song_info['songs'][0]
                url_data = url_info['data'][0]
                song_name = song_data['name']
                artist_name = ', '.join(a['name'] for a in song_data['ar'])

                task_manager.update_task(task.task_id, name=song_name, extra={
                    'artist': artist_name, 'album': song_data['al']['name'],
                    'quality': actual_quality,
                })

                include_quality = getattr(config, 'download_quality_in_filename', True)
                base_name = f"{artist_name} - {song_name}"
                if include_quality:
                    safe_fn = f"{base_name} [{_QUALITY_LABELS.get(actual_quality, actual_quality)}]"
                else:
                    safe_fn = base_name
                safe_fn = ''.join(c for c in safe_fn if c not in r'<>:"/\|?*')
                filename = f"{safe_fn}.{url_data['type']}"
                download_url = url_data['url']

                # 模式3: 仅本地
                if save_local and not browser_download:
                    file_path = download_dir / filename
                    if file_path.exists():
                        task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED,
                                                 message='文件已存在', progress=100)
                    else:
                        task_manager.update_task(task.task_id, message='正在后台下载...', progress=50)
                        def _bg():
                            try:
                                r = requests.get(download_url, stream=True, timeout=60)
                                r.raise_for_status()
                                with open(file_path, 'wb') as f:
                                    for c in r.iter_content(chunk_size=8192):
                                        f.write(c)
                                task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED,
                                                         message='下载完成', progress=100)
                            except Exception as e:
                                task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                                         message='下载失败', error=str(e))
                        Thread(target=_bg, daemon=True).start()

                    return APIResponse.success({
                        'music_id': music_id, 'name': song_name, 'artist': artist_name,
                        'album': song_data['al']['name'], 'quality': quality,
                        'file_type': url_data['type'], 'file_size': url_data['size'],
                        'filename': filename, 'mode': 'local_only',
                    }, "已开始后台保存到本地")

                # 模式1&2: 流式代理
                local_f = None
                if save_local:
                    file_path = download_dir / filename
                    local_f = open(file_path, 'wb')

                def stream_proxy():
                    try:
                        r = requests.get(download_url, stream=True, timeout=60)
                        r.raise_for_status()
                        for chunk in r.iter_content(chunk_size=65536):
                            if local_f:
                                local_f.write(chunk)
                            yield chunk
                        task_manager.update_task(task.task_id, status=TaskStatus.COMPLETED,
                                                 message='下载完成', progress=100)
                    except Exception as e:
                        task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                                 message='下载失败', error=str(e))
                    finally:
                        if local_f:
                            local_f.close()

                resp = Response(stream_with_context(stream_proxy()),
                                mimetype=f"audio/{url_data['type']}")
                resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
                resp.headers['X-Download-Filename'] = quote(filename, safe='')
                return resp

            except Exception as inner_e:
                task_manager.update_task(task.task_id, status=TaskStatus.FAILED,
                                         message='下载过程出错', error=str(inner_e))
                raise

        except Exception as e:
            api_service.logger.error(f"下载音乐异常: {e}\n{traceback.format_exc()}")
            return APIResponse.error(f"下载异常: {str(e)}", 500)
