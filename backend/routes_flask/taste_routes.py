"""
音乐口味雷达 / DNA 谱图 / AI 标签路由
"""

import sqlite3
import threading
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import request

from backend.api_core import APIResponse
from backend.music_api import url_v1, name_v1, lyric_v1
from backend.task_manager import task_manager, TaskStatus
from backend.auth import get_current_user, login_required


def register_taste_routes(app, api_service, _PROJECT_ROOT):
    """注册口味雷达/DNA路由"""

    @app.route('/api/user/<username>/taste-radar', methods=['GET'])
    @login_required
    def api_taste_radar(username):
        try:
            db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
            if not db_path.exists():
                return APIResponse.success({'radar': [50] * 10, 'count': 0}, "暂无特征数据")

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            cur = conn.execute("PRAGMA table_info(track_audio_features)")
            columns = {row[1] for row in cur.fetchall()}

            def col_avg(name, fallback=50):
                if name in columns:
                    return f"ROUND(AVG(COALESCE(f.{name}, {fallback})))"
                return str(fallback)

            sql_physical = f"""
                SELECT {col_avg('score_tempo')}, {col_avg('score_energy')},
                       {col_avg('score_brightness')}, {col_avg('score_energy_contrast')},
                       {col_avg('score_sub_bass')}, {col_avg('score_vocal_dominant')},
                       {col_avg('score_lyric_sentiment')}
                FROM user_track_behaviors b
                INNER JOIN track_audio_features f ON b.track_id = f.track_id
                WHERE b.username = ? AND b.is_favorite = 1
            """
            cur = conn.execute(sql_physical, (username,))
            row = cur.fetchone()
            physical = [int(v) for v in row] if row else [50] * 7

            cur = conn.execute(
                "SELECT COUNT(*) FROM user_track_behaviors WHERE username=? AND is_favorite=1",
                (username,))
            total = cur.fetchone()[0] or 1

            # 空间氛围感
            cur = conn.execute("""
                SELECT COUNT(DISTINCT tt.track_id) FROM user_track_behaviors b
                JOIN track_tags tt ON tt.track_id = b.track_id
                WHERE b.username = ? AND b.is_favorite = 1 AND tt.tag_name = 'Ambient music'
            """, (username,))
            amb_cnt = cur.fetchone()[0] or 0
            ambiance = min(100, round(amb_cnt / total * 100)) if amb_cnt > 0 else int(round((100 - physical[1]) * 0.5 + (100 - physical[3]) * 0.5))

            # 纯器乐倾向
            cur = conn.execute("""
                SELECT COUNT(DISTINCT tt.track_id) FROM user_track_behaviors b
                JOIN track_tags tt ON tt.track_id = b.track_id
                WHERE b.username = ? AND b.is_favorite = 1 AND tt.tag_name = 'Classical music'
            """, (username,))
            inst_cnt = cur.fetchone()[0] or 0
            vocal_avg = physical[5] if len(physical) > 5 else 50
            instrumental = min(100, round(inst_cnt / total * 100)) if inst_cnt > 0 else int(round((100 - physical[1]) * 0.4 + (100 - vocal_avg) * 0.6))

            # 文化主题共鸣
            cur = conn.execute("""
                SELECT COUNT(DISTINCT tt.track_id) FROM user_track_behaviors b
                JOIN track_tags tt ON tt.track_id = b.track_id
                WHERE b.username = ? AND b.is_favorite = 1 AND tt.category = 'llm'
                  AND (tt.tag_name LIKE '%国风%' OR tt.tag_name LIKE '%江湖%' OR tt.tag_name LIKE '%古风%')
            """, (username,))
            cult_cnt = cur.fetchone()[0] or 0
            cultural = min(100, round(cult_cnt / total * 100)) if cult_cnt > 0 else int(round((100 - physical[1]) * 0.3 + physical[2] * 0.3 + physical[6] * 0.4))

            conn.close()
            radar = physical + [ambiance, instrumental, cultural]

            if total > 0:
                return APIResponse.success({'radar': radar, 'count': total},
                                           f"DNA 谱图数据获取成功（{total}首）")
            return APIResponse.success({'radar': [50] * 10, 'count': 0}, "暂无喜欢歌曲数据")
        except Exception as e:
            api_service.logger.error(f"DNA 谱图异常: {e}")
            return APIResponse.success({'radar': [50] * 10, 'count': 0}, f"获取失败: {str(e)}")

    @app.route('/api/user/<username>/taste-top-tracks', methods=['GET'])
    @login_required
    def api_taste_top_tracks(username):
        try:
            db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
            if not db_path.exists():
                return APIResponse.success([], "暂无数据")

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT mt.id AS track_id, mt.title, mt.artist, mt.file_path,
                       ROUND((COALESCE(f.score_tempo,50) + COALESCE(f.score_energy,50) +
                              COALESCE(f.score_brightness,50) + COALESCE(f.score_energy_contrast,50) +
                              COALESCE(f.score_sub_bass,50) + COALESCE(f.score_vocal_dominant,50) +
                              COALESCE(f.score_lyric_sentiment,50)) / 7.0, 1) AS resonance
                FROM user_track_behaviors b
                INNER JOIN track_audio_features f ON b.track_id = f.track_id
                INNER JOIN music_tracks mt ON mt.id = b.track_id
                WHERE b.username = ? AND b.is_favorite = 1
                ORDER BY resonance DESC LIMIT 50
            """, (username,))
            rows = cur.fetchall()
            conn.close()

            tracks = [{
                'rank': i + 1, 'track_id': str(r['track_id']),
                'title': r['title'], 'artist': r['artist'],
                'file_path': r['file_path'], 'resonance': r['resonance'],
            } for i, r in enumerate(rows)]
            return APIResponse.success(tracks, f"TOP {len(tracks)} 共鸣单曲")
        except Exception as e:
            return APIResponse.success([], f"获取失败: {str(e)}")

    @app.route('/api/user/<username>/taste-top-tags', methods=['GET'])
    @login_required
    def api_taste_top_tags(username):
        try:
            db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
            if not db_path.exists():
                return APIResponse.success([], "暂无数据")
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT tt.tag_name, tt.category, COUNT(*) AS freq,
                       ROUND(AVG(tt.confidence)) AS avg_confidence
                FROM user_track_behaviors b
                JOIN track_tags tt ON tt.track_id = b.track_id
                WHERE b.username = ? AND b.is_favorite = 1
                GROUP BY tt.tag_name, tt.category ORDER BY freq DESC LIMIT 20
            """, (username,))
            rows = cur.fetchall()
            conn.close()
            tags = [{'tag_name': r['tag_name'], 'category': r['category'],
                     'freq': r['freq'], 'avg_confidence': r['avg_confidence']} for r in rows]
            return APIResponse.success(tags, f"TOP {len(tags)} 标签")
        except Exception as e:
            return APIResponse.success([], f"获取失败: {str(e)}")

    @app.route('/api/tags/<tag_name>/tracks', methods=['GET'])
    @login_required
    def api_tag_tracks(tag_name):
        try:
            from urllib.parse import unquote
            tag_name = unquote(tag_name)
            db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
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
                ORDER BY tt.confidence DESC LIMIT 50
            """, (username or 'admin', tag_name))
            rows = cur.fetchall()
            conn.close()
            tracks = [{'track_id': r['track_id'], 'title': r['title'],
                       'artist': r['artist'], 'file_path': r['file_path'],
                       'confidence': r['confidence'], 'is_favorite': bool(r['is_favorite'])}
                      for r in rows]
            return APIResponse.success(tracks, f"标签 '{tag_name}' 关联 {len(tracks)} 首歌曲")
        except Exception as e:
            return APIResponse.success([], f"获取失败: {str(e)}")

    # ── DNA 重建 ──
    @app.route('/api/user/<username>/taste-rebuild', methods=['POST'])
    @login_required
    def api_taste_rebuild(username):
        task = task_manager.create_task('dna_rebuild', 'DNA雷达重建', username=username)
        thread = threading.Thread(
            target=_dna_rebuild_worker,
            args=(task.task_id, username),
            daemon=True,
            name=f'dna-rebuild-{task.task_id}',
        )
        thread.start()
        return APIResponse.success({'task_id': task.task_id}, "重建任务已启动")


def _dna_rebuild_worker(task_id: str, username: str):
    """3线程并行下载+分析我喜欢歌单中的歌曲"""
    from backend.main import api_service, _PROJECT_ROOT, _liked_ids_cache, _fetch_liked_ids_direct
    from backend.playback_api import _load_netease_cookies

    try:
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

        db_path = _PROJECT_ROOT / 'config' / 'music_vault.db'
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("DELETE FROM user_track_behaviors WHERE username = ?", (username,))
            conn.commit()
            conn.close()
        except Exception as e:
            api_service.logger.warning(f"[DNA重建] 清空旧数据失败（继续）: {e}")

        task_manager.update_task(task_id, status=TaskStatus.RUNNING,
                                 progress=0, message=f'共 {total} 首，3线程并行处理中')

        cookies = _load_netease_cookies()
        completed = 0
        skipped = 0
        failed = 0
        cancel_lock = threading.Lock()
        progress_lock = threading.Lock()

        def _check_cancelled():
            t = task_manager.get_task(task_id)
            return t is not None and t.status == TaskStatus.CANCELLED

        def _process_one(track_id: int):
            nonlocal completed, skipped, failed
            with cancel_lock:
                if _check_cancelled():
                    return 'cancelled'
            try:
                detail = name_v1(track_id) or {}
                songs = detail.get('songs', [])
                if songs:
                    title = songs[0].get('name', f'track_{track_id}')
                    ar = songs[0].get('ar', [])
                    artist = ', '.join(a.get('name', '') for a in ar) if ar else ''
                else:
                    title = f'track_{track_id}'
                    artist = ''

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

                if not cookies:
                    with progress_lock:
                        failed += 1
                        completed += 1
                    return 'no_cookies'

                url_result = url_v1(track_id, 'exhigh', cookies)
                song_url = None
                if isinstance(url_result, dict):
                    data_list = url_result.get('data', [])
                    song_url = data_list[0].get('url', '') if data_list else ''
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

                from services.song_storage import SongStorageService
                storage = SongStorageService()
                metadata = {'track_id': str(track_id), 'song_name': title}
                try:
                    store_path, _ = storage.download_and_store(username, song_url, metadata)
                except Exception:
                    with progress_lock:
                        failed += 1
                        completed += 1
                    return 'download_failed'

                from music_processor.single_scorer import score_single_track
                try:
                    score_single_track(str(store_path), title=title, artist=artist,
                                       album='', username=username)
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

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {executor.submit(_process_one, tid): tid for tid in liked_ids}
            for future in as_completed(future_map):
                if _check_cancelled():
                    for f in future_map:
                        f.cancel()
                    break
                try:
                    future.result()
                except Exception:
                    pass
                with progress_lock:
                    pct = int(completed / total * 100) if total else 0
                    task_manager.update_task(task_id, progress=pct,
                                             message=f'{completed}/{total} | 跳过:{skipped} 失败:{failed}')

        with cancel_lock:
            if _check_cancelled():
                task_manager.update_task(task_id, status=TaskStatus.CANCELLED,
                                         message=f'用户取消 | 已处理 {completed}/{total}')
                return

        task_manager.update_task(task_id, status=TaskStatus.COMPLETED, progress=100,
                                 message=f'完成 {completed}/{total} | 跳过:{skipped} 失败:{failed}')
    except Exception as e:
        api_service.logger.error(f"DNA rebuild 异常: {e}")
        task_manager.update_task(task_id, status=TaskStatus.FAILED,
                                 message='异常中断', error=str(e))
