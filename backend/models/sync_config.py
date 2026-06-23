"""
歌单同步配置模型 — 纯数据类，与持久化解耦
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PlaylistSyncConfig:
    """歌单同步配置"""
    playlist_ids: List[str]
    quality: str = "lossless"
    sync_interval: int = 3600
    cron_expression: Optional[str] = None
    download_dir: str = "downloads"
    max_concurrent: int = 3
    cookie_file: Optional[str] = None
    sync_full_delete: bool = False
    sync_dedup_files: bool = False


@dataclass
class SyncResult:
    """单歌单同步结果"""
    playlist_id: str
    playlist_name: str = ""
    success: bool = False
    total_tracks: int = 0
    synced_count: int = 0
    replaced_count: int = 0
    failed_count: int = 0
    sync_time: str = ""
    error: str = ""
    remote_stems: set = field(default_factory=set)
