"""
PlaylistSyncService — 歌单同步业务逻辑（重构版）

职责：
- 编排定时调度、歌单解析、下载、历史记录
- 委托 Repository 做持久化
- 委托 MusicAPI/Downloader 做外部调用
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List, Set

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from models.sync_config import PlaylistSyncConfig, SyncResult
from repositories.sync_history_repo import SyncHistoryRepository
from music_api import playlist_detail, name_v1, url_v1, APIException
from cookie_manager import CookieManager, CookieException
from music_downloader import MusicDownloader, DownloadException
from event_bus import event_bus, EventType, fire_event, create_event
from lyrics_db import LyricsDB, save_lrc_file

logger = logging.getLogger("playlist_sync_service")


class PlaylistSyncService:
    """歌单同步服务"""

    AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".wma"}

    def __init__(self, config: PlaylistSyncConfig):
        self.config = config
        self.cookie_manager = CookieManager(
            cookie_file=config.cookie_file if config.cookie_file else None
        )
        self.downloader = MusicDownloader(
            download_dir=config.download_dir, max_concurrent=config.max_concurrent
        )
        self.downloads_path = Path(config.download_dir)
        self.downloads_path.mkdir(exist_ok=True)
        self.sync_history_repo = SyncHistoryRepository(self.downloads_path)
        self.scheduler = BackgroundScheduler()
        logger.info("歌单同步服务初始化完成")

    # ── 生命周期 ──

    def start(self):
        """启动定时调度"""
        trigger = (
            CronTrigger.from_crontab(self.config.cron_expression)
            if self.config.cron_expression
            else IntervalTrigger(seconds=self.config.sync_interval)
        )
        self.scheduler.add_job(
            func=self.sync_all_playlists,
            trigger=trigger,
            id="playlist_sync_job",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("歌单同步调度已启动")
        Thread(target=self.sync_all_playlists, daemon=True).start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    # ── 同步入口 ──

    def sync_all_playlists(self) -> List[Dict]:
        """同步所有配置的歌单，返回结果列表"""
        logger.info(f"开始同步 {len(self.config.playlist_ids)} 个歌单")
        fire_event(EventType.SYNC_STARTED, {
            'playlist_count': len(self.config.playlist_ids),
            'quality': self.config.quality,
        }, source='playlist_sync', async_mode=True)

        results: List[Dict] = []
        all_remote_stems: Set[str] = set()

        for pid in self.config.playlist_ids:
            try:
                r = self.sync_single_playlist(pid.strip())
                results.append(r)
                if r.get('remote_stems'):
                    all_remote_stems.update(r['remote_stems'])
            except Exception as e:
                logger.error(f"同步歌单 {pid} 异常: {e}")
                results.append({'playlist_id': pid, 'success': False, 'error': str(e)})

        # 后处理：去重 & 清理
        dedup_count = self._dedup_by_md5() if getattr(self.config, 'sync_dedup_files', False) else 0
        deleted_count = self._delete_extra_local(all_remote_stems) if getattr(self.config, 'sync_full_delete', False) and all_remote_stems else 0

        # 保存历史
        self.sync_history_repo.save(results)

        # 事件
        ok = sum(1 for r in results if r['success'])
        fire_event(EventType.SYNC_COMPLETED if ok == len(results) else EventType.SYNC_FAILED, {
            'success_count': ok, 'total_count': len(results),
            'deleted_count': deleted_count,
        }, source='playlist_sync', async_mode=True)

        logger.info(f"同步完成: {ok}/{len(results)}")
        return results

    def sync_single_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """同步单个歌单"""
        fire_event(EventType.SYNC_PLAYLIST_STARTED, {'playlist_id': playlist_id}, source='playlist_sync', async_mode=True)
        try:
            cookies = self.cookie_manager.parse_cookies()
            if not cookies:
                raise CookieException("无有效 Cookie")
            playlist = playlist_detail(playlist_id, cookies)
            if not playlist or 'tracks' not in playlist:
                raise APIException("获取歌单详情失败")

            tracks = playlist.get('tracks', [])
            existing_ids = self.sync_history_repo.get_all_synced_ids()
            local_stems, local_exts = self._scan_local_files()
            synced, failed, skipped_hist, skipped_local, replaced = 0, 0, 0, 0, 0
            new_ids: List[str] = []

            for track in tracks:
                sid = str(track.get('id', ''))
                name = track.get('name', '')
                artists = track.get('artists', '')
                stem = self._build_stem(artists, name)

                if sid in existing_ids:
                    skipped_hist += 1
                    self._ensure_lyrics(sid, name, artists, cookies)
                    continue
                if stem in local_stems:
                    expected_ext = self._expected_ext()
                    if expected_ext in local_exts.get(stem, set()):
                        skipped_local += 1
                        existing_ids.add(sid)
                        self._ensure_lyrics(sid, name, artists, cookies, stem)
                        continue
                    else:
                        self._delete_by_stem(stem, local_exts.get(stem, set()))
                        replaced += 1

                # 下载
                result = self.downloader.download_music_file(music_id=sid, quality=self.config.quality, cookies=cookies)
                if result.success:
                    synced += 1
                    existing_ids.add(sid)
                    new_ids.append(sid)
                else:
                    failed += 1
                time.sleep(0.5)

            remote_stems = {self._build_stem(t.get('artists', ''), t.get('name', '')) for t in tracks}
            fire_event(EventType.SYNC_PLAYLIST_COMPLETED, {
                'playlist_id': playlist_id, 'playlist_name': playlist.get('name', ''),
                'synced_count': synced, 'replaced_count': replaced, 'failed_count': failed,
                'remote_track_count': len(remote_stems),
            }, source='playlist_sync', async_mode=True)

            return {
                'playlist_id': playlist_id, 'playlist_name': playlist.get('name', ''),
                'success': True, 'total_tracks': len(tracks),
                'synced_count': synced, 'replaced_count': replaced, 'failed_count': failed,
                'synced_ids': new_ids, 'remote_stems': remote_stems,
                'sync_time': datetime.now().isoformat(),
            }
        except Exception as e:
            return {'playlist_id': playlist_id, 'success': False, 'error': str(e)}

    # ── 内部工具 ──

    def _build_stem(self, artists: str, title: str) -> str:
        return ''.join(c for c in f"{artists} - {title}" if c not in r'<>:"/\|?*')

    def _expected_ext(self) -> str:
        return ".flac" if self.config.quality in ("lossless", "hires", "jymaster") else ".mp3"

    def _scan_local_files(self) -> tuple[Set[str], Dict[str, Set[str]]]:
        stems, exts = set(), {}
        for f in self.downloads_path.rglob("*"):
            if f.suffix.lower() in self.AUDIO_EXTENSIONS:
                stem = f.stem
                stems.add(stem)
                exts.setdefault(stem, set()).add(f.suffix.lower())
        return stems, exts

    def _delete_by_stem(self, stem: str, extensions: Set[str]) -> None:
        for ext in extensions:
            f = self.downloads_path / f"{stem}{ext}"
            if f.exists():
                f.unlink()

    def _dedup_by_md5(self) -> int:
        """MD5 去重"""
        count = 0
        seen: Dict[str, Path] = {}
        for f in sorted(self.downloads_path.rglob("*"), key=lambda x: x.stat().st_size if x.is_file() else 0, reverse=True):
            if f.suffix.lower() not in self.AUDIO_EXTENSIONS:
                continue
            try:
                h = hashlib.md5(f.read_bytes()[:8192]).hexdigest()
                if h in seen:
                    f.unlink()
                    count += 1
                else:
                    seen[h] = f
            except OSError:
                pass
        return count

    def _delete_extra_local(self, remote_stems: Set[str]) -> int:
        count = 0
        for f in self.downloads_path.rglob("*"):
            if f.suffix.lower() in self.AUDIO_EXTENSIONS and f.stem not in remote_stems:
                f.unlink()
                count += 1
        return count

    def _ensure_lyrics(self, song_id: str, name: str, artists: str, cookies: dict, stem: str = ""):
        """确保歌词已保存到 DB"""
        try:
            from music_api import lyric_v1
            lyric = lyric_v1(song_id, cookies)
            if lyric:
                lrc = lyric.get('lrc', {}).get('lyric', '')
                tlyric = lyric.get('tlyric', {}).get('lyric', '')
                db = LyricsDB()
                import json
                db.save_lyric(song_id=song_id, song_name=name, artist=artists, album='',
                              original_lyric=lrc, translated_lyric=tlyric,
                              lyric_raw=json.dumps(lyric, ensure_ascii=False))
                if stem:
                    save_lrc_file(self.downloads_path, stem, lrc, tlyric)
        except Exception:
            pass

    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        history = self.sync_history_repo.load()
        return {
            'service_running': self.scheduler.running,
            'job_count': len(self.scheduler.get_jobs()),
            'config': {
                'playlist_ids': self.config.playlist_ids,
                'quality': self.config.quality,
                'sync_interval': self.config.sync_interval,
                'cron_expression': self.config.cron_expression or '',
                'download_dir': str(self.downloads_path),
            },
            'history': history,
        }
