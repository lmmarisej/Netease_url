"""
SyncHistoryRepository — 同步历史记录持久化

职责：读写 downloads/{user}/sync_history.json，记录已下载歌曲 ID。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger("sync_history_repo")


class SyncHistoryRepository:
    """同步历史记录仓库"""

    def __init__(self, download_dir: str | Path):
        self._history_file = Path(download_dir) / "sync_history.json"

    def load(self) -> Dict[str, List[str]]:
        """加载同步历史，返回 {playlist_id: [song_id, ...]}"""
        try:
            if self._history_file.exists():
                with open(self._history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"读取同步历史失败: {e}")
        return {}

    def save(self, results: List[Dict]) -> None:
        """保存同步结果到历史文件"""
        try:
            existing = self.load()
            for result in results:
                if result.get("success") and result.get("playlist_id"):
                    pid = result["playlist_id"]
                    existing[pid] = result.get("synced_ids", [])
            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"保存同步历史失败: {e}")

    def get_all_synced_ids(self) -> Set[str]:
        """获取所有已同步的歌曲 ID 集合"""
        history = self.load()
        ids: Set[str] = set()
        for song_ids in history.values():
            ids.update(song_ids)
        return ids
