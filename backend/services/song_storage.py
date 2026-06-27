"""
song_storage.py — 歌曲存储服务层
===============================
封装内容寻址存储 (CAS) + 用户映射表操作。
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from repositories.song_store_repo import SongStoreRepo, get_song_store

logger = logging.getLogger("song_storage")

# ────────────────────────── 路径 ──────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DB_PATH = _PROJECT_ROOT / "config" / "music_vault.db"
_DOWNLOADS_DIR = _PROJECT_ROOT / "downloads"
_STORE_DIR = _DOWNLOADS_DIR / "_store"
_STORE_DIR_NAME = "_store"

# ────────────────────────── SQL 迁移 ──────────────────────────

_MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS user_song_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    original_filename TEXT DEFAULT '',
    title       TEXT DEFAULT '',
    artist      TEXT DEFAULT '',
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_user_songs_username
    ON user_song_files(username);

CREATE INDEX IF NOT EXISTS idx_user_songs_hash
    ON user_song_files(content_hash);
"""


def ensure_user_song_table(db_path: Optional[str] = None) -> None:
    """幂等建表：user_song_files（已存在则跳过）"""
    path = db_path or str(_DB_PATH)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_MIGRATION_SQL)
        conn.commit()
        logger.info("user_song_files 表就绪")
    finally:
        conn.close()


# ═══════════════ SongStorageService ═══════════════


class SongStorageService:
    """
    歌曲存储服务。

    职责：
      1. 下载 + CAS 去重存储
      2. 用户 → 歌曲 映射维护
      3. 统计信息查询
    """

    CHUNK_SIZE = 65536
    REQUEST_TIMEOUT = 120

    def __init__(self, store: Optional[SongStoreRepo] = None):
        self.store = store or get_song_store()
        ensure_user_song_table()

    # ═══════════════ 下载 + 存储 ═══════════════

    def download_and_store(
        self,
        username: str,
        download_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Path, str]:
        """
        下载文件到临时目录 → 计算 MD5 → CAS 去重 → 写入用户映射。

        Args:
            username: 用户名
            download_url: 文件下载 URL
            metadata: {title, artist, ext, ...}

        Returns:
            (store_path, content_hash)
        """
        meta = metadata or {}
        title = meta.get("title", "")
        artist = meta.get("artist", "")
        ext = meta.get("ext", "mp3").lstrip(".")

        # ── Step 1: 下载到临时文件 ──
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}", prefix="dl_")
        os.close(tmp_fd)
        tmp_file = Path(tmp_path)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://music.163.com/",
            }
            r = requests.get(download_url, headers=headers, stream=True, timeout=self.REQUEST_TIMEOUT)
            r.raise_for_status()

            total_bytes = 0
            with open(tmp_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                    f.write(chunk)
                    total_bytes += len(chunk)

            logger.info(f"下载完成: {total_bytes / 1048576:.1f}MB → {tmp_file.name}")

            # ── Step 2: 计算 MD5 ──
            content_hash = self.store.compute_md5(tmp_file)
            logger.debug(f"MD5: {content_hash}")

            # ── Step 3: CAS 存储 ──
            dest, is_new = self.store.atomic_move(
                src_path=tmp_file,
                content_hash=content_hash,
                ext=ext,
                metadata={
                    "title": title,
                    "artist": artist,
                    "size": total_bytes,
                },
            )
            action = "新增" if is_new else "去重"

            # ── Step 4: 用户映射 ──
            self._link_user_song(
                username=username,
                content_hash=content_hash,
                original_filename=meta.get("filename", f"{title}.{ext}"),
                title=title,
                artist=artist,
            )

            logger.info(f"存储完成 [{action}]: {title} - {artist} | hash={content_hash[:12]}")
            return dest, content_hash

        except Exception as e:
            # 清理临时文件
            tmp_file.unlink(missing_ok=True)
            logger.error(f"下载存储失败: {e}")
            raise

    # ═══════════════ 直接存储已有文件 ═══════════════

    def store_existing_file(
        self,
        username: str,
        file_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Path, str]:
        """
        将已存在的文件移入 CAS 存储。

        适用于存量迁移场景。
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        meta = metadata or {}
        ext = meta.get("ext", file_path.suffix.lstrip("."))
        content_hash = self.store.compute_md5(file_path)

        dest, is_new = self.store.atomic_move(
            src_path=file_path,
            content_hash=content_hash,
            ext=ext,
            metadata={"title": meta.get("title", ""), "artist": meta.get("artist", ""), "size": meta.get("size", 0)},
        )

        self._link_user_song(
            username=username,
            content_hash=content_hash,
            original_filename=file_path.name,
            title=meta.get("title", ""),
            artist=meta.get("artist", ""),
        )

        return dest, content_hash

    # ═══════════════ 用户映射 ═══════════════

    def _link_user_song(
        self,
        username: str,
        content_hash: str,
        original_filename: str = "",
        title: str = "",
        artist: str = "",
    ) -> None:
        """INSERT OR IGNORE 用户歌曲映射"""
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            conn.execute(
                """INSERT OR IGNORE INTO user_song_files
                   (username, content_hash, original_filename, title, artist)
                   VALUES (?, ?, ?, ?, ?)""",
                (username, content_hash, original_filename, title, artist),
            )
            conn.commit()
        finally:
            conn.close()

    def get_user_songs(self, username: str) -> List[Dict[str, Any]]:
        """查询用户的所有歌曲映射"""
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM user_song_files WHERE username = ? ORDER BY added_at DESC",
                (username,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def resolve_user_song(self, username: str, content_hash: str) -> Optional[Path]:
        """
        根据用户名和哈希解析物理路径。

        用于文件流式播放：先从 user_song_files 获取哈希，
        再从 _store 解析路径。
        """
        conn = sqlite3.connect(str(_DB_PATH))
        row = conn.execute(
            "SELECT 1 FROM user_song_files WHERE username = ? AND content_hash = ?",
            (username, content_hash),
        ).fetchone()
        conn.close()
        if not row:
            return None
        # 从索引获取扩展名
        return self.store.resolve_path(content_hash, self.store._index.get(content_hash, {}).get("ext", "mp3"))

    def get_store_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        return self.store.get_stats()

    # ═══════════════ 存量迁移 ═══════════════

    def migrate_existing_files(
        self,
        dry_run: bool = False,
        target_username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        扫描现有 downloads/{user}/ 目录，将音频文件移入 _store。

        Args:
            dry_run: True 时仅预览，不实际移动文件
            target_username: 仅迁移指定用户目录，None=全部

        Returns:
            { migrated: int, skipped: int, saved_bytes: int, errors: [...] }
        """
        stats = {"migrated": 0, "skipped": 0, "saved_bytes": 0, "errors": []}

        # 扫描用户目录
        user_dirs = []
        if target_username:
            d = _DOWNLOADS_DIR / target_username
            if d.is_dir():
                user_dirs.append((target_username, d))
        else:
            for item in _DOWNLOADS_DIR.iterdir():
                if item.is_dir() and item.name != _STORE_DIR_NAME and not item.name.startswith("."):
                    user_dirs.append((item.name, item))

        audio_exts = {".mp3", ".flac", ".m4a", ".wav", ".ogg", ".aac", ".wma"}

        for username, user_dir in user_dirs:
            audio_files = []
            for ext in audio_exts:
                audio_files.extend(user_dir.rglob(f"*{ext}"))
            audio_files = sorted(set(audio_files))

            logger.info(f"扫描 {username}: {len(audio_files)} 个音频文件")

            for file_path in audio_files:
                try:
                    file_size = file_path.stat().st_size

                    if dry_run:
                        # 干运行：计算哈希但不移动
                        content_hash = self.store.compute_md5(file_path) if file_size > 0 else ""
                        if self.store.has_content(content_hash):
                            stats["skipped"] += 1
                            stats["saved_bytes"] += file_size
                        else:
                            stats["migrated"] += 1
                        logger.info(f"[DRY RUN] {file_path.name}: hash={content_hash[:12]}")
                    else:
                        # 实际迁移
                        ext = file_path.suffix.lstrip(".")
                        # 从文件名推断元数据: "Artist - Title [Quality].ext"
                        stem = file_path.stem
                        parts = stem.split(" - ", 1)
                        artist = parts[0] if len(parts) > 1 else ""
                        title = parts[1].split(" [")[0] if len(parts) > 1 else stem

                        self.store_existing_file(
                            username=username,
                            file_path=file_path,
                            metadata={
                                "title": title,
                                "artist": artist,
                                "ext": ext,
                                "size": file_size,
                            },
                        )
                        stats["migrated"] += 1

                except Exception as e:
                    err_msg = f"{file_path.name}: {e}"
                    logger.error(f"迁移失败: {err_msg}")
                    stats["errors"].append(err_msg)

        if dry_run:
            logger.info(
                f"[预览] 将迁移 {stats['migrated']} 个新文件，"
                f"跳过 {stats['skipped']} 个已存在（节省 {stats['saved_bytes'] / 1048576:.1f}MB）"
            )
        else:
            logger.info(f"迁移完成: {stats['migrated']} 文件, {len(stats['errors'])} 错误")

        return stats


# ────────────────────────── 单例 ──────────────────────────

_storage_service: Optional[SongStorageService] = None


def get_song_storage_service() -> SongStorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = SongStorageService()
    return _storage_service
