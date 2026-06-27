"""
PlaybackLogService — 听歌行为埋点业务逻辑

职责：
- 接收播放事件
- 计算 is_skipped 状态（播放时长 < 阈值 且 完成率 < 10%）
- 委托 Repository 写入数据库
"""

from __future__ import annotations

import logging
from typing import Optional

from models.domain import PlaybackEvent, TrackBehavior
from repositories.track_repo import TrackRepository

logger = logging.getLogger("playback_log_service")


class PlaybackLogService:
    """听歌行为埋点服务"""

    def __init__(self, track_repo: TrackRepository | None = None):
        self._track_repo = track_repo or TrackRepository()

    # ── 埋点写入 ──

    def log_playback(
        self,
        track_id: int,
        username: str,
        play_duration_sec: float,
        total_duration_sec: float = 0.0,
        skip_threshold_sec: float = 5.0,
    ) -> None:
        """
        记录一次播放行为。

        Args:
            track_id: 歌曲 ID
            username: 用户名
            play_duration_sec: 实际播放时长（秒）
            total_duration_sec: 歌曲总时长（秒），0 表示未知
            skip_threshold_sec: 跳过阈值（秒），小于此值视为跳过
        """
        event = PlaybackEvent(
            track_id=track_id,
            username=username,
            play_duration_sec=play_duration_sec,
            total_duration_sec=total_duration_sec,
            skip_threshold_sec=skip_threshold_sec,
        )
        logger.info(
            f"播放埋点: track={track_id}, user={username}, "
            f"duration={play_duration_sec:.1f}s, skipped={event.is_skipped}"
        )
        self._track_repo.upsert_behavior(event)

    # ── 行为查询 ──

    def get_behavior(self, track_id: int, username: str) -> Optional[TrackBehavior]:
        """获取单曲用户行为"""
        return self._track_repo.get_behavior(track_id, username)

    def get_favorites(self, username: str) -> list:
        """获取用户收藏"""
        return self._track_repo.get_favorites(username)

    def toggle_favorite(self, track_id: int, username: str, is_favorite: bool) -> None:
        """切换收藏状态"""
        self._track_repo.set_favorite(track_id, username, is_favorite)
