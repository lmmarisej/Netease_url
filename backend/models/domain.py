"""
领域数据类 — 与持久化无关的纯数据结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PlaybackEvent:
    """听歌行为埋点事件"""
    track_id: int
    username: str
    play_duration_sec: float          # 实际播放时长（秒）
    total_duration_sec: float = 0.0   # 歌曲总时长（秒），0 表示未知
    is_skipped: bool = False
    skip_threshold_sec: float = 5.0   # 小于此秒数视为跳过

    def __post_init__(self):
        if not self.is_skipped and self.total_duration_sec > 0:
            self.is_skipped = (
                self.play_duration_sec < self.skip_threshold_sec and
                self.play_duration_sec / max(self.total_duration_sec, 1) < 0.1
            )


@dataclass
class TrackBehavior:
    """用户对单曲的行为聚合"""
    track_id: int
    username: str
    is_favorite: bool = True
    completion_rate: float = 1.0
    skip_count: int = 0
    play_count: int = 0
    last_played_at: str = ""
