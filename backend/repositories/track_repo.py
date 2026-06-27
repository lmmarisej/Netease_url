"""
TrackRepository — 歌曲行为数据访问层（SQLite）

职责：封装对 music_vault.db 中 user_track_behaviors 表的 CRUD。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.domain import PlaybackEvent, TrackBehavior

logger = logging.getLogger("track_repo")


class TrackRepository:
    """歌曲行为数据仓库"""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent.parent.parent / "config" / "music_vault.db"
        self._db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── 行为写入 ──

    def upsert_behavior(self, event: PlaybackEvent) -> None:
        """记录听歌行为（INSERT OR REPLACE）"""
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT skip_count, completion_rate, last_played_at "
                "FROM user_track_behaviors WHERE track_id=? AND username=?",
                (event.track_id, event.username),
            ).fetchone()

            if existing:
                new_skip = existing["skip_count"] + (1 if event.is_skipped else 0)
                # 取最高完成率
                new_rate = existing["completion_rate"]
                if event.total_duration_sec > 0:
                    current = event.play_duration_sec / event.total_duration_sec
                    new_rate = max(new_rate, current)
                conn.execute(
                    "UPDATE user_track_behaviors SET skip_count=?, completion_rate=?, "
                    "last_played_at=datetime('now') WHERE track_id=? AND username=?",
                    (new_skip, min(new_rate, 1.0), event.track_id, event.username),
                )
            else:
                conn.execute(
                    "INSERT INTO user_track_behaviors (track_id, username, is_favorite, "
                    "completion_rate, skip_count, last_played_at) VALUES (?,?,1,?,?,datetime('now'))",
                    (event.track_id, event.username,
                     event.play_duration_sec / max(event.total_duration_sec, 1) if event.total_duration_sec > 0 else 1.0,
                     1 if event.is_skipped else 0),
                )
            conn.commit()

    # ── 行为查询 ──

    def get_behavior(self, track_id: int, username: str) -> Optional[TrackBehavior]:
        """获取单曲用户行为"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_track_behaviors WHERE track_id=? AND username=?",
                (track_id, username),
            ).fetchone()
            if not row:
                return None
            return TrackBehavior(
                track_id=row["track_id"],
                username=row["username"],
                is_favorite=bool(row["is_favorite"]),
                completion_rate=row["completion_rate"] or 0.0,
                skip_count=row["skip_count"] or 0,
                play_count=1,
                last_played_at=row["last_played_at"] or "",
            )

    def get_favorites(self, username: str) -> List[Dict[str, Any]]:
        """获取用户收藏列表"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ub.*, mt.title, mt.artist, mt.file_path "
                "FROM user_track_behaviors ub "
                "JOIN music_tracks mt ON mt.id = ub.track_id "
                "WHERE ub.username=? AND ub.is_favorite=1",
                (username,),
            ).fetchall()
            return [dict(r) for r in rows]

    def set_favorite(self, track_id: int, username: str, is_favorite: bool) -> None:
        """设置/取消收藏"""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO user_track_behaviors (track_id, username, is_favorite) "
                "VALUES (?,?,?) ON CONFLICT(track_id, username) DO UPDATE SET is_favorite=?",
                (track_id, username, int(is_favorite), int(is_favorite)),
            )
            conn.commit()
