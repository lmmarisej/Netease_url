"""SQLite 数据库初始化 — 四表分离架构 (WAL 模式)。"""

import sqlite3
from pathlib import Path


def init_database(db_path: Path) -> sqlite3.Connection:
    """创建 WAL 模式数据库及 4 张业务领域表。"""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # 表 1: 核心元数据
    conn.execute("""
        CREATE TABLE IF NOT EXISTS music_tracks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT NOT NULL UNIQUE,
            title       TEXT,
            artist      TEXT,
            album       TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 表 2: 音频特征评分 (1:1)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS track_audio_features (
            track_id              INTEGER PRIMARY KEY,
            score_tempo           INTEGER,
            score_energy          INTEGER,
            score_brightness      INTEGER,
            score_rhythm          INTEGER,
            score_tonality        INTEGER,
            score_energy_contrast INTEGER,
            score_lyric_sentiment INTEGER DEFAULT 50,
            updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(track_id) REFERENCES music_tracks(id) ON DELETE CASCADE
        )
    """)

    # 表 3: AI 语义标签
    conn.execute("""
        CREATE TABLE IF NOT EXISTS track_tags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id    INTEGER NOT NULL,
            tag_name    TEXT NOT NULL,
            confidence  INTEGER NOT NULL,
            category    TEXT NOT NULL DEFAULT 'panns',
            UNIQUE(track_id, tag_name, category),
            FOREIGN KEY(track_id) REFERENCES music_tracks(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tags_name_conf
        ON track_tags(tag_name, confidence)
    """)

    # 表 4: 用户交互行为埋点
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_track_behaviors (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id        INTEGER NOT NULL,
            username        TEXT NOT NULL DEFAULT 'admin',
            is_favorite     INTEGER DEFAULT 1,
            completion_rate REAL DEFAULT 1.0,
            skip_count      INTEGER DEFAULT 0,
            last_played_at  TEXT,
            UNIQUE(track_id, username),
            FOREIGN KEY(track_id) REFERENCES music_tracks(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_behaviors_user_fav
        ON user_track_behaviors(username, is_favorite)
    """)

    conn.commit()
    return conn
