"""定时任务调度器模块

提供网易云音乐歌单定时同步功能，包括：
- 定时同步指定歌单到本地
- 支持多种音质选择
- 自动下载新歌
- 同步日志记录
"""

import os
import re
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from music_api import playlist_detail, name_v1, url_v1, APIException
from cookie_manager import CookieManager, CookieException
from music_downloader import MusicDownloader, DownloadException
from event_bus import event_bus, EventType, fire_event, create_event


class PlaylistSyncConfig:
    """歌单同步配置类"""
    
    def __init__(
        self,
        playlist_ids: List[str],
        quality: str = "lossless",
        sync_interval: int = 3600,
        cron_expression: Optional[str] = None,
        download_dir: str = "downloads",
        max_concurrent: int = 3,
        cookie_file: Optional[str] = None
    ):
        self.playlist_ids = playlist_ids
        self.quality = quality
        self.sync_interval = sync_interval
        self.cron_expression = cron_expression
        self.download_dir = download_dir
        self.max_concurrent = max_concurrent
        self.cookie_file = cookie_file


class PlaylistSyncService:
    """歌单同步服务类"""
    
    def __init__(self, config: PlaylistSyncConfig):
        """
        初始化歌单同步服务
        
        Args:
            config: 同步配置对象
        """
        self.config = config
        self.logger = self._setup_logger()
        self.cookie_manager = CookieManager(
            cookie_file=config.cookie_file if config.cookie_file else None
        )
        self.downloader = MusicDownloader(
            download_dir=config.download_dir,
            max_concurrent=config.max_concurrent
        )
        
        # 创建下载目录
        self.downloads_path = Path(config.download_dir)
        self.downloads_path.mkdir(exist_ok=True)
        
        # 同步历史记录文件
        self.sync_history_file = self.downloads_path / "sync_history.json"
        
        # 初始化调度器
        self.scheduler = BackgroundScheduler()
        
        self.logger.info("歌单同步服务初始化完成")
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('playlist_sync')
        logger.setLevel(logging.INFO)
        
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
                logs_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'logs'
                logs_dir.mkdir(exist_ok=True)
                log_file = logs_dir / 'playlist_sync.log'
                file_handler = RotatingFileHandler(
                    str(log_file),
                    maxBytes=2 * 1024 * 1024,
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
    
    def start(self):
        """启动定时同步服务"""
        try:
            # 添加定时任务
            if self.config.cron_expression:
                # 使用Cron表达式
                trigger = CronTrigger.from_crontab(self.config.cron_expression)
                self.logger.info(f"使用Cron表达式: {self.config.cron_expression}")
            else:
                # 使用固定间隔
                trigger = IntervalTrigger(seconds=self.config.sync_interval)
                self.logger.info(f"使用固定间隔: {self.config.sync_interval}秒")
            
            self.scheduler.add_job(
                func=self.sync_all_playlists,
                trigger=trigger,
                id='playlist_sync_job',
                name='歌单同步任务',
                replace_existing=True
            )
            
            # 启动调度器
            self.scheduler.start()
            self.logger.info("歌单同步服务已启动")
            
            # 立即执行一次同步
            self.logger.info("执行首次同步...")
            Thread(target=self.sync_all_playlists, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"启动同步服务失败: {e}\n{traceback.format_exc()}")
            raise
    
    def stop(self):
        """停止定时同步服务"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                self.logger.info("歌单同步服务已停止")
        except Exception as e:
            self.logger.error(f"停止同步服务失败: {e}")
    
    def sync_all_playlists(self):
        """同步所有配置的歌单"""
        self.logger.info("="*60)
        self.logger.info(f"开始同步 {len(self.config.playlist_ids)} 个歌单")
        self.logger.info("="*60)

        # 触发同步开始事件
        fire_event(EventType.SYNC_STARTED, {
            'playlist_count': len(self.config.playlist_ids),
            'quality': self.config.quality,
        }, source='playlist_sync', async_mode=True)
        
        sync_results = []
        
        for playlist_id in self.config.playlist_ids:
            try:
                result = self.sync_single_playlist(playlist_id.strip())
                sync_results.append(result)
            except Exception as e:
                self.logger.error(f"同步歌单 {playlist_id} 异常: {e}\n{traceback.format_exc()}")
                sync_results.append({
                    'playlist_id': playlist_id,
                    'success': False,
                    'error': str(e),
                    'synced_count': 0
                })
        
        # 记录同步总结
        success_count = sum(1 for r in sync_results if r['success'])
        total_synced = sum(r.get('synced_count', 0) for r in sync_results)
        
        self.logger.info("="*60)
        self.logger.info(f"同步完成: 成功 {success_count}/{len(sync_results)}, 共下载 {total_synced} 首歌曲")
        self.logger.info("="*60)
        
        # 保存同步历史
        self._save_sync_history(sync_results)

        # 触发同步完成/失败事件
        if success_count == len(sync_results):
            fire_event(EventType.SYNC_COMPLETED, {
                'success_count': success_count,
                'total_count': len(sync_results),
                'total_synced': total_synced,
            }, source='playlist_sync', async_mode=True)
        else:
            fire_event(EventType.SYNC_FAILED, {
                'success_count': success_count,
                'total_count': len(sync_results),
                'total_synced': total_synced,
                'error': f"{len(sync_results) - success_count} 个歌单同步失败",
            }, source='playlist_sync', async_mode=True)
        
        return sync_results
    
    def sync_single_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """同步单个歌单
        
        Args:
            playlist_id: 歌单ID
            
        Returns:
            同步结果字典
        """
        self.logger.info(f"\n开始同步歌单: {playlist_id}")

        fire_event(EventType.SYNC_PLAYLIST_STARTED, {
            'playlist_id': playlist_id,
        }, source='playlist_sync', async_mode=True)
        
        try:
            # 获取Cookie
            cookies = self.cookie_manager.parse_cookies()
            if not cookies:
                raise CookieException("未找到有效的Cookie")
            
            # 获取歌单详情
            playlist_info = playlist_detail(playlist_id, cookies)
            
            if not playlist_info or 'tracks' not in playlist_info:
                raise APIException("获取歌单详情失败")
            
            playlist_name = playlist_info.get('name', f'歌单_{playlist_id}')
            tracks = playlist_info.get('tracks', [])
            
            self.logger.info(f"歌单名称: {playlist_name}")
            self.logger.info(f"歌曲总数: {len(tracks)}")
            
            # 获取已存在的歌曲列表（同步历史 + 本地文件扫描）
            existing_songs = self._get_existing_songs()
            local_stems = self._get_local_file_stems()
            self.logger.info(f"本地已有音频文件: {len(local_stems)} 个")
            
            # 下载新歌曲
            synced_count = 0
            failed_count = 0
            skipped_by_history = 0
            skipped_by_local = 0
            
            for i, track in enumerate(tracks, 1):
                try:
                    song_id = track.get('id')
                    song_name = track.get('name', '未知歌曲')
                    artists = track.get('artists', '未知艺术家')
                    
                    # 检查同步历史
                    if song_id in existing_songs:
                        self.logger.debug(f"[{i}/{len(tracks)}] 跳过(历史): {song_name} - {artists}")
                        skipped_by_history += 1
                        continue
                    
                    # 检查本地是否已有文件（差集比对，无需 API 调用）
                    expected_stem = self._build_expected_stem(artists, song_name)
                    if expected_stem in local_stems:
                        self.logger.info(f"[{i}/{len(tracks)}] 跳过(本地已有): {song_name} - {artists}")
                        existing_songs.add(song_id)  # 同步到历史记录
                        skipped_by_local += 1
                        continue
                    
                    # 下载歌曲
                    self.logger.info(f"[{i}/{len(tracks)}] 下载: {song_name} - {artists}")
                    
                    download_result = self.downloader.download_music_file(
                        music_id=song_id,
                        quality=self.config.quality
                    )
                    
                    if download_result.success:
                        synced_count += 1
                        existing_songs.add(song_id)
                        self.logger.info(f"✓ 下载成功: {download_result.file_path}")
                        fire_event(EventType.SYNC_SONG_DOWNLOADED, {
                            'playlist_id': playlist_id,
                            'song_id': song_id,
                            'song_name': song_name,
                            'artists': artists,
                            'progress': f"{i}/{len(tracks)}",
                        }, source='playlist_sync', async_mode=True)
                    else:
                        failed_count += 1
                        self.logger.warning(f"✗ 下载失败: {download_result.error_message}")
                    
                    # 避免请求过快
                    time.sleep(0.5)
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"下载歌曲失败: {e}")
                    continue
            
            self.logger.info(f"歌单 '{playlist_name}' 同步完成: 新增 {synced_count} 首, 跳过(历史) {skipped_by_history} 首, 跳过(本地) {skipped_by_local} 首, 失败 {failed_count} 首")

            fire_event(EventType.SYNC_PLAYLIST_COMPLETED, {
                'playlist_id': playlist_id,
                'playlist_name': playlist_name,
                'total_tracks': len(tracks),
                'synced_count': synced_count,
                'failed_count': failed_count,
            }, source='playlist_sync', async_mode=True)
            
            return {
                'playlist_id': playlist_id,
                'playlist_name': playlist_name,
                'success': True,
                'total_tracks': len(tracks),
                'synced_count': synced_count,
                'failed_count': failed_count,
                'sync_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"同步歌单 {playlist_id} 失败: {e}\n{traceback.format_exc()}")
            return {
                'playlist_id': playlist_id,
                'success': False,
                'error': str(e),
                'sync_time': datetime.now().isoformat()
            }
    
    def _get_existing_songs(self) -> set:
        """获取已存在的歌曲ID集合（通过同步历史记录判断）"""
        existing_songs = set()
        
        try:
            # 读取同步历史
            if self.sync_history_file.exists():
                import json
                with open(self.sync_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    for record in history.get('synced_songs', []):
                        existing_songs.add(record)
        except Exception as e:
            self.logger.warning(f"读取同步历史失败: {e}")
        
        return existing_songs
    
    def _sanitize_for_match(self, name: str) -> str:
        """清理文件名用于匹配（与 MusicDownloader._sanitize_filename 逻辑一致）
        
        Args:
            name: 原始名称
            
        Returns:
            清理后的小写名称
        """
        illegal_chars = r'[<>:"/\\|?*]'
        name = re.sub(illegal_chars, '_', name)
        name = name.strip(' .')
        if len(name) > 200:
            name = name[:200]
        return name.lower() or "unknown"
    
    def _get_local_file_stems(self) -> Set[str]:
        """扫描下载目录，获取所有本地文件的文件名主干（不含扩展名）
        
        一次性扫描整个 downloads 目录，返回小写文件名主干的集合，
        用于与歌单歌曲进行批量差集比对，避免逐曲目的文件系统检查。
        
        Returns:
            小写文件名主干集合，如 {"周杰伦 - 晴天", "林俊杰 - 江南"}
        """
        stems = set()
        try:
            if not self.downloads_path.exists():
                return stems
            
            for entry in self.downloads_path.iterdir():
                if entry.is_file():
                    # 只收集音频文件，跳过 sync_history.json 等非音频文件
                    suffix = entry.suffix.lower()
                    if suffix in ('.mp3', '.flac', '.m4a', '.wav', '.ogg', '.wma'):
                        stems.add(entry.stem.lower())
        except Exception as e:
            self.logger.warning(f"扫描本地文件失败: {e}")
        
        return stems
    
    def _build_expected_stem(self, artists: str, song_name: str) -> str:
        """根据艺术家和歌曲名构建预期的文件名主干
        
        与 MusicDownloader.download_music_file 中的文件名生成逻辑保持一致：
        {艺术家} - {歌曲名}，经过相同的 sanitize 处理。
        
        Args:
            artists: 艺术家字符串（如 "周杰伦" 或 "A/B"）
            song_name: 歌曲名称
            
        Returns:
            预期的小写文件名主干，如 "周杰伦 - 晴天"
        """
        raw = f"{artists} - {song_name}"
        return self._sanitize_for_match(raw)
    
    def _save_sync_history(self, sync_results: List[Dict[str, Any]]):
        """保存同步历史记录"""
        try:
            import json
            
            history = {
                'last_sync_time': datetime.now().isoformat(),
                'sync_results': sync_results,
                'synced_songs': list(self._get_existing_songs())
            }
            
            with open(self.sync_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"同步历史已保存: {self.sync_history_file}")
            
        except Exception as e:
            self.logger.error(f"保存同步历史失败: {e}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态信息"""
        try:
            is_running = self.scheduler.running
            jobs = self.scheduler.get_jobs()
            
            status = {
                'service_running': is_running,
                'job_count': len(jobs),
                'config': {
                    'playlist_ids': self.config.playlist_ids,
                    'quality': self.config.quality,
                    'sync_interval': self.config.sync_interval,
                    'cron_expression': self.config.cron_expression,
                    'download_dir': str(self.downloads_path.absolute())
                }
            }
            
            # 读取同步历史
            if self.sync_history_file.exists():
                import json
                with open(self.sync_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    status['last_sync'] = history.get('last_sync_time')
                    status['total_synced_songs'] = len(history.get('synced_songs', []))
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取同步状态失败: {e}")
            return {
                'service_running': False,
                'error': str(e)
            }


# 全局同步服务实例
sync_service: Optional[PlaylistSyncService] = None


def init_sync_service(config: PlaylistSyncConfig) -> PlaylistSyncService:
    """初始化全局同步服务"""
    global sync_service
    sync_service = PlaylistSyncService(config)
    return sync_service


def get_sync_service() -> Optional[PlaylistSyncService]:
    """获取全局同步服务实例"""
    return sync_service
