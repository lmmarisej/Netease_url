"""事务内持久化流水线 — 单首歌曲的完整写入。"""

import sqlite3
from datetime import datetime

from . import config
from . import scoring
from . import sentiment


def persist_track(
    conn: sqlite3.Connection,
    file_path: str,
    meta: dict,
    features: dict,
    lyrics: str | None,
    panns_tags: list[dict],
    username: str = "admin",
) -> tuple:
    """
    单首歌曲完整持久化流水线（调用方事务内执行）：

    1. INSERT OR IGNORE music_tracks → 获取 track_id
    2. INSERT OR REPLACE track_audio_features（7 维评分）
    3. DELETE 旧标签 + INSERT track_tags
    4. INSERT OR IGNORE user_track_behaviors（绝不覆盖用户行为数据）

    Returns: (s_tempo, s_energy, s_bright, s_rhythm, s_tonal,
              s_contrast, s_sentiment, panns_tags)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 写入元数据 / 获取 track_id
    conn.execute(
        "INSERT OR IGNORE INTO music_tracks (file_path, title, artist, album) "
        "VALUES (?, ?, ?, ?)",
        (file_path, meta["title"], meta["artist"], meta["album"]),
    )
    cur = conn.execute(
        "SELECT id FROM music_tracks WHERE file_path = ?", (file_path,)
    )
    track_id = cur.fetchone()[0]

    # 2. 7 维评分
    s_tempo     = scoring.score_tempo(features["tempo"])
    s_energy    = scoring.score_energy(features["rms_mean"])
    s_bright    = scoring.score_brightness(features["centroid_mean"])
    s_rhythm_v  = scoring.score_rhythm(features["zcr_mean"])
    s_tonal     = scoring.score_tonality(features["mfcc_mean"])
    s_contrast  = scoring.score_energy_contrast(features["rms_std"])
    s_sentiment = sentiment.score_lyric_sentiment(lyrics)

    conn.execute("""
        INSERT OR REPLACE INTO track_audio_features
            (track_id, score_tempo, score_energy, score_brightness,
             score_rhythm, score_tonality, score_energy_contrast,
             score_lyric_sentiment, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (track_id, s_tempo, s_energy, s_bright, s_rhythm_v, s_tonal,
          s_contrast, s_sentiment, now))

    # 3. AI 标签
    conn.execute("DELETE FROM track_tags WHERE track_id = ?", (track_id,))
    if panns_tags:
        conn.executemany(
            "INSERT OR REPLACE INTO track_tags "
            "(track_id, tag_name, confidence, category) "
            "VALUES (?, ?, ?, 'panns')",
            [(track_id, t["tag_name"], t["confidence"]) for t in panns_tags],
        )

    # 4. 行为埋点（INSERT OR IGNORE — 绝不覆盖 Node.js 写入的真实数据）
    conn.execute(
        "INSERT OR IGNORE INTO user_track_behaviors "
        "(track_id, username) VALUES (?, ?)",
        (track_id, username),
    )

    return (s_tempo, s_energy, s_bright, s_rhythm_v, s_tonal,
            s_contrast, s_sentiment, panns_tags)
