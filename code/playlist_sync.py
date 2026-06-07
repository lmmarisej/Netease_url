"""定时任务调度器模块

提供网易云音乐歌单定时同步功能，包括：
- 定时同步指定歌单到本地
- 支持多种音质选择
- 自动下载新歌
- 同步日志记录
"""

import os
import time
import logging
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from music_api import playlist_detail, name_v1, url_v1, APIException
from cookie_manager import CookieManager, CookieException
from music_downloader import MusicDownloader, DownloadException


class PlaylistSyncConfig:
    """歌单同步配置类"""
    
    def __init__(
        self,
        playlist_ids: List[str],
        quality: str = "lossless",
        sync_interval: int = 3600,
        cron_expression: Optional[str] = None,
        download_dir: str = "downloads",
        max_concurrent: int = 3
    ):
        """
        初始化同步配置
        
        Args:
            playlist_ids: 需要同步的歌单ID列表
            quality: 下载音质 (standard/exhigh/lossless/hires/sky/jyeffect/jymaster)
            sync_interval: 同步间隔（秒），默认3600秒（1小时）
            cron_expression: Cron表达式，如果设置则优先使用
            download_dir: 下载目录
            max_concurrent: 最大并发下载数
        """
        self.playlist_ids = playlist_ids
        self.quality = quality
        self.sync_interval = sync_interval
        self.cron_expression = cron_expression
        self.download_dir = download_dir
        self.max_concurrent = max_concurrent


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
        self.cookie_manager = CookieManager()
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
            
            # 文件处理器
            try:
                logs_dir = Path('logs')
                logs_dir.mkdir(exist_ok=True)
                log_file = logs_dir / 'playlist_sync.log'
                file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
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
        
        return sync_results
    
    def sync_single_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """同步单个歌单
        
        Args:
            playlist_id: 歌单ID
            
        Returns:
            同步结果字典
        """
        self.logger.info(f"\n开始同步歌单: {playlist_id}")
        
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
            
            # 获取已存在的歌曲列表
            existing_songs = self._get_existing_songs()
            
            # 下载新歌曲
            synced_count = 0
            failed_count = 0
            
            for i, track in enumerate(tracks, 1):
                try:
                    song_id = track.get('id')
                    song_name = track.get('name', '未知歌曲')
                    artists = track.get('artists', '未知艺术家')
                    
                    # 检查是否已存在
                    if song_id in existing_songs:
                        self.logger.debug(f"[{i}/{len(tracks)}] 跳过已存在: {song_name} - {artists}")
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
                    else:
                        failed_count += 1
                        self.logger.warning(f"✗ 下载失败: {download_result.error_message}")
                    
                    # 避免请求过快
                    time.sleep(0.5)
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"下载歌曲失败: {e}")
                    continue
            
            self.logger.info(f"歌单 '{playlist_name}' 同步完成: 新增 {synced_count} 首, 失败 {failed_count} 首")
            
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
        """获取已存在的歌曲ID集合（通过文件名判断）"""
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
