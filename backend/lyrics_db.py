"""歌词数据库模块

使用 SQLite 存储网易云音乐歌词，支持：
- 按歌曲ID存储/查询歌词（原始 + 翻译）
- 关键字搜索歌词
- 分页列表查询
- username 字段做用户维度数据隔离（单库）
- 导出 .lrc 歌词文件到歌曲同目录
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta

# 中国时区
CST = timezone(timedelta(hours=8))

logger = logging.getLogger(__name__)


def _get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent


def get_lyrics_db_path() -> Path:
    """获取歌词数据库路径（单一共享数据库）

    Returns:
        数据库文件路径
    """
    db_path = _get_project_root() / 'config' / 'lyrics.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


class LyricsDB:
    """歌词数据库管理类（单库 + username 字段隔离）"""

    # 表结构 — username 字段用于用户维度隔离
    TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS lyrics (
        song_id         INTEGER NOT NULL,
        username        TEXT    NOT NULL DEFAULT '',
        song_name       TEXT    NOT NULL DEFAULT '',
        artist          TEXT    NOT NULL DEFAULT '',
        album           TEXT    NOT NULL DEFAULT '',
        original_lyric  TEXT    NOT NULL DEFAULT '',
        translated_lyric TEXT   NOT NULL DEFAULT '',
        lyric_raw       TEXT    NOT NULL DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT '',
        updated_at      TEXT    NOT NULL DEFAULT '',
        PRIMARY KEY (song_id, username)
    )
    """

    # 搜索索引
    INDEX_SCHEMA = """
    CREATE INDEX IF NOT EXISTS idx_lyrics_username
        ON lyrics(username);
    CREATE INDEX IF NOT EXISTS idx_lyrics_song_name
        ON lyrics(song_name);
    CREATE INDEX IF NOT EXISTS idx_lyrics_artist
        ON lyrics(artist);
    CREATE INDEX IF NOT EXISTS idx_lyrics_album
        ON lyrics(album);
    """

    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: 数据库文件路径，默认 config/lyrics.db
        """
        self.db_path = Path(db_path) if db_path else get_lyrics_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(self.TABLE_SCHEMA)
            conn.executescript(self.INDEX_SCHEMA)
            conn.commit()
            conn.close()
            logger.info(f"歌词数据库已初始化: {self.db_path}")
        except Exception as e:
            logger.error(f"初始化歌词数据库失败: {e}")
            raise

        self.username = ''  # 当前操作用户，由调用方设置

    def set_user(self, username: str) -> None:
        """设置当前操作用户"""
        self.username = username or ''

    def _now_iso(self) -> str:
        """获取当前时间的 ISO 8601 字符串"""
        return datetime.now(CST).strftime('%Y-%m-%dT%H:%M:%S+08:00')

    # ==================== 写入 ====================

    def save_lyric(
        self,
        song_id: int,
        song_name: str = '',
        artist: str = '',
        album: str = '',
        original_lyric: str = '',
        translated_lyric: str = '',
        lyric_raw: str = '',
        username: str = '',
    ) -> bool:
        """保存或更新歌词（UPSERT，按 song_id + username 唯一）

        Returns:
            是否保存成功
        """
        try:
            user = username or self.username
            conn = sqlite3.connect(str(self.db_path))
            now = self._now_iso()
            conn.execute(
                """INSERT INTO lyrics
                   (song_id, username, song_name, artist, album,
                    original_lyric, translated_lyric, lyric_raw,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(song_id, username) DO UPDATE SET
                    song_name=excluded.song_name,
                    artist=excluded.artist,
                    album=excluded.album,
                    original_lyric=excluded.original_lyric,
                    translated_lyric=excluded.translated_lyric,
                    lyric_raw=excluded.lyric_raw,
                    updated_at=excluded.updated_at""",
                (song_id, user, song_name, artist, album,
                 original_lyric, translated_lyric, lyric_raw,
                 now, now)
            )
            conn.commit()
            conn.close()
            logger.debug(f"歌词已保存: song_id={song_id}, user={user}, name={song_name}")
            return True
        except Exception as e:
            logger.error(f"保存歌词失败 (song_id={song_id}): {e}")
            return False

    # ==================== 查询 ====================

    def get_lyric(self, song_id: int, username: str = '') -> Optional[Dict[str, Any]]:
        """根据歌曲 ID 和用户名查询歌词"""
        try:
            user = username or self.username
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM lyrics WHERE song_id = ? AND username = ?", (song_id, user)
            ).fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"查询歌词失败 (song_id={song_id}): {e}")
            return None

    def search_lyrics(
        self,
        keyword: str,
        limit: int = 50,
        offset: int = 0,
        username: str = '',
    ) -> Tuple[List[Dict[str, Any]], int]:
        """搜索歌词（模糊匹配 + 用户过滤）"""
        try:
            user = username or self.username
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            like = f"%{keyword}%"

            total_row = conn.execute(
                """SELECT COUNT(*) as cnt FROM lyrics
                   WHERE username = ? AND (
                     song_name LIKE ? OR artist LIKE ?
                     OR album LIKE ? OR original_lyric LIKE ?
                     OR translated_lyric LIKE ?)""",
                (user, like, like, like, like, like)
            ).fetchone()
            total = total_row['cnt'] if total_row else 0

            rows = conn.execute(
                """SELECT * FROM lyrics
                   WHERE username = ? AND (
                     song_name LIKE ? OR artist LIKE ?
                     OR album LIKE ? OR original_lyric LIKE ?
                     OR translated_lyric LIKE ?)
                   ORDER BY updated_at DESC
                   LIMIT ? OFFSET ?""",
                (user, like, like, like, like, like, limit, offset)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows], total
        except Exception as e:
            logger.error(f"搜索歌词失败 (keyword={keyword}): {e}")
            return [], 0

    def get_all_lyrics(
        self,
        limit: int = 50,
        offset: int = 0,
        username: str = '',
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取歌词列表（分页 + 用户过滤）"""
        try:
            user = username or self.username
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row

            total_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM lyrics WHERE username = ?", (user,)
            ).fetchone()
            total = total_row['cnt'] if total_row else 0

            rows = conn.execute(
                """SELECT * FROM lyrics WHERE username = ?
                   ORDER BY updated_at DESC
                   LIMIT ? OFFSET ?""",
                (user, limit, offset)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows], total
        except Exception as e:
            logger.error(f"获取歌词列表失败: {e}")
            return [], 0

    # ==================== 删除 ====================

    def delete_lyric(self, song_id: int, username: str = '') -> bool:
        """删除指定歌曲的歌词"""
        try:
            user = username or self.username
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "DELETE FROM lyrics WHERE song_id = ? AND username = ?", (song_id, user)
            )
            conn.commit()
            conn.close()
            logger.info(f"歌词已删除: song_id={song_id}, user={user}")
            return True
        except Exception as e:
            logger.error(f"删除歌词失败 (song_id={song_id}): {e}")
            return False

    def get_count(self, username: str = '') -> int:
        """获取歌词总数"""
        try:
            user = username or self.username
            conn = sqlite3.connect(str(self.db_path))
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM lyrics WHERE username = ?", (user,)
            ).fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"获取歌词数量失败: {e}")
            return 0


# ==================== LRC 文件导出 ====================

def save_lrc_file(music_dir: Path, safe_filename: str, original_lyric: str,
                  translated_lyric: str = '') -> Optional[Path]:
    """保存 .lrc 歌词文件到歌曲同目录

    Args:
        music_dir: 歌曲所在目录
        safe_filename: 已清理的安全文件名（不含扩展名）
        original_lyric: 原始歌词（LRC 格式）
        translated_lyric: 翻译歌词（可选）

    Returns:
        .lrc 文件路径，失败返回 None
    """
    if not original_lyric and not translated_lyric:
        return None
    try:
        lrc_path = music_dir / f"{safe_filename}.lrc"
        content = original_lyric or ''
        if translated_lyric:
            if content:
                content += '\n\n'
            content += translated_lyric
        lrc_path.write_text(content, encoding='utf-8')
        logger.info(f"歌词文件已保存: {lrc_path}")
        return lrc_path
    except Exception as e:
        logger.warning(f"保存歌词文件失败: {e}")
        return None


# ==================== 全局便捷函数 ====================

def save_lyric_from_music_info(
    music_info,
    lyric_raw: str = '',
    username: str = '',
    save_lrc: bool = True,
    music_filename: str = '',
    music_dir: str = '',
) -> bool:
    """从 MusicInfo 对象保存歌词到 SQLite + 可选导出 .lrc 文件

    Args:
        music_info: MusicInfo 对象
        lyric_raw: 原始 API JSON 响应字符串
        username: 当前用户名
        save_lrc: 是否同时导出 .lrc 文件
        music_filename: 歌曲安全文件名（不含扩展名），用于 .lrc 命名
        music_dir: 歌曲下载目录

    Returns:
        是否保存成功
    """
    db = LyricsDB()
    ok = db.save_lyric(
        song_id=music_info.id,
        song_name=music_info.name,
        artist=music_info.artists,
        album=music_info.album,
        original_lyric=music_info.lyric or '',
        translated_lyric=music_info.tlyric or '',
        lyric_raw=lyric_raw,
        username=username,
    )
    # 同时导出 .lrc 文件
    if save_lrc and ok and music_filename and music_dir:
        save_lrc_file(
            Path(music_dir), music_filename,
            music_info.lyric or '', music_info.tlyric or ''
        )
    return ok
