"""
single_scorer.py — 单首歌曲打分流水线
===================================
用于推荐流后台异步处理：
  1. librosa 7 维声学特征提取
  2. 6 大物理评分维度映射
  3. SnowNLP 歌词情感分析
  4. PANNs CNN14 标签识别
  5. Ollama LLM 歌词意境分析
  6. 事务内持久化写入 DB
  7. 返回 10 维特征向量 + preference_score

被 _async_download_and_score() 调用（threading.Thread 后台执行）。
"""

from __future__ import annotations

import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── 项目根目录 ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DB_PATH = _PROJECT_ROOT / "config" / "music_vault.db"

# ── 10 维特征 key ──
FEATURE_KEYS = [
    "tempo", "energy", "vocal_ratio", "bass_intensity", "acousticness",
    "electronic_score", "rock_score", "instrument_pureness",
    "midnight_emo", "guofeng_vibe",
]


def score_single_track(
    file_path: str,
    title: str = "",
    artist: str = "",
    album: str = "",
    username: str = "admin",
) -> Dict[str, Any]:
    """
    单首歌曲完整打分流水线。

    Args:
        file_path: 音频文件绝对路径
        title: 歌曲名
        artist: 歌手名
        album: 专辑名
        username: 用户名

    Returns:
        {
            "track_id": int,           # DB 中的 track ID
            "features": {10维特征},     # 0-100 浮点
            "preference_score": int,    # 偏好匹配分
            "scores": {7维评分},        # tempo/energy/...
            "panns_tags": [...],        # PANNs 标签
            "llm_tags": [...],          # LLM 意境标签
        }
    """
    from . import features as feats
    from . import metadata as meta_mod
    from . import sentiment
    from . import scoring
    from . import panns
    from . import llm
    from . import persistence

    result: Dict[str, Any] = {
        "track_id": 0,
        "features": {},
        "preference_score": 0,
        "scores": {},
        "panns_tags": [],
        "llm_tags": [],
    }

    # ── Step 1: 元数据提取 ──
    meta = meta_mod.extract_metadata(file_path) if title == "" else {
        "title": title, "artist": artist, "album": album,
    }

    # ── Step 2: librosa 特征 ──
    features = feats.extract_features(file_path)
    if features is None:
        print(f"[single_scorer] 特征提取失败: {file_path}")
        return result

    # ── Step 3: 歌词提取 + 情感分析 ──
    lyrics = meta_mod.extract_lyrics(file_path)
    sentiment_score = sentiment.score_lyric_sentiment(lyrics)

    # ── Step 4: PANNs 标签 ──
    panns_tags: List[dict] = []
    try:
        panns_tags = panns.extract_panns_tags(file_path)
    except Exception:
        print(f"[single_scorer] PANNs 跳过: {traceback.format_exc(limit=1)}")

    # ── Step 5: LLM 歌词意境 ──
    llm_tags: List[str] = []
    if lyrics and len(lyrics.strip()) >= 20:
        try:
            llm_tags = llm.analyze_lyrics_via_llm(lyrics)
        except Exception:
            print(f"[single_scorer] LLM 跳过: {traceback.format_exc(limit=1)}")

    # ── Step 6: 事务内持久化 ──
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        scores = persistence.persist_track(
            conn, file_path, meta, features, lyrics,
            panns_tags, llm_tags, username,
        )
        conn.commit()

        s_tempo, s_energy, s_bright, s_rhythm_v, s_tonal, s_contrast, \
            s_sentiment, pts, ltags = scores

        result["scores"] = {
            "tempo": s_tempo, "energy": s_energy,
            "brightness": s_bright, "rhythm": s_rhythm_v,
            "tonality": s_tonal, "contrast": s_contrast,
            "sentiment": s_sentiment,
        }
        result["panns_tags"] = pts
        result["llm_tags"] = ltags

        # ── Step 7: 获取 track_id 并构建 10 维特征向量 ──
        cur = conn.execute(
            "SELECT id FROM music_tracks WHERE file_path = ?", (file_path,)
        )
        row = cur.fetchone()
        if row:
            track_id = row[0]
            result["track_id"] = track_id

        # 查询特征 + 标签
        conn.row_factory = sqlite3.Row
        feats_row = conn.execute(
            "SELECT * FROM track_audio_features WHERE track_id = ?",
            (track_id,),
        ).fetchone()
        tags_rows = conn.execute(
            "SELECT tag_name, confidence, category FROM track_tags WHERE track_id = ?",
            (track_id,),
        ).fetchall()

        feature_vec = _build_feature_vector_from_row(feats_row, tags_rows)
        result["features"] = feature_vec

        # ── Step 8: 计算 preference_score ──
        pref = _compute_pref_from_features(feature_vec)
        result["preference_score"] = pref

        print(
            f"[single_scorer] 完成: {meta['title']} - {meta['artist']}, "
            f"pref_score={pref}"
        )

    except Exception:
        print(f"[single_scorer] 持久化失败: {traceback.format_exc()}")
        conn.rollback()
    finally:
        conn.close()

    return result


def _build_feature_vector_from_row(
    feats_row: Optional[sqlite3.Row],
    tags_rows: List[sqlite3.Row],
) -> Dict[str, float]:
    """从 DB 行构建 10 维特征向量（复用 playback_api._build_feature_vector 逻辑）。"""
    # 标签映射表
    _ELECTRONIC_TAGS = {
        "electronic", "electronic music", "edm", "synth", "synthwave",
        "techno", "house", "trance", "dubstep", "ambient electronic",
        "electronica", "dance", "electro",
    }
    _ROCK_TAGS = {
        "rock", "rock music", "metal", "heavy metal", "punk", "hard rock",
        "alternative rock", "indie rock", "grunge",
    }
    _ACOUSTIC_TAGS = {
        "acoustic", "acoustic guitar", "folk", "unplugged", "orchestra",
        "classical", "piano", "chamber music", "strings",
    }
    _INSTRUMENTAL_TAGS = {
        "instrumental", "no vocals", "pure music", "orchestral",
        "classical", "jazz", "ambient",
    }
    _MIDNIGHT_EMO_TAGS = {
        "失恋", "孤独", "暗黑", "悲伤", "emo", "melancholy",
        "depression", "sad", "heartbreak", "分手", "深夜",
        "忧郁", "压抑", "绝望", "伤感", "lonely",
    }
    _GUOFENG_TAGS = {
        "国风", "古韵", "中国风", "古风", "民族", "传统",
        "戏曲", "民乐", "水墨", "江湖", "武侠",
    }

    def _tag_score(tags: List[sqlite3.Row], match_set: set) -> float:
        best = 0.0
        for t in tags:
            tag_name = t["tag_name"].lower() if t["tag_name"] else ""
            if tag_name in match_set:
                conf = float(t["confidence"]) if t["confidence"] else 0.5
                if t["category"] == "panns":
                    conf = conf * 100.0
                else:
                    conf = min(conf + 30.0, 95.0) if best > 0 else 55.0
                if conf > best:
                    best = conf
        return min(best, 100.0)

    if feats_row:
        tempo = float(feats_row["score_tempo"] or 50)
        energy = float(feats_row["score_energy"] or 50)
        vocal_ratio = float(feats_row["score_vocal_dominant"] or 50)
        bass_intensity = float(feats_row["score_sub_bass"] or 50)
    else:
        tempo = energy = vocal_ratio = bass_intensity = 50.0

    return {
        "tempo": round(tempo, 1),
        "energy": round(energy, 1),
        "vocal_ratio": round(vocal_ratio, 1),
        "bass_intensity": round(bass_intensity, 1),
        "acousticness": round(_tag_score(tags_rows, _ACOUSTIC_TAGS), 1),
        "electronic_score": round(_tag_score(tags_rows, _ELECTRONIC_TAGS), 1),
        "rock_score": round(_tag_score(tags_rows, _ROCK_TAGS), 1),
        "instrument_pureness": round(_tag_score(tags_rows, _INSTRUMENTAL_TAGS), 1),
        "midnight_emo": round(_tag_score(tags_rows, _MIDNIGHT_EMO_TAGS), 1),
        "guofeng_vibe": round(_tag_score(tags_rows, _GUOFENG_TAGS), 1),
    }


def _compute_pref_from_features(features: Dict[str, float]) -> int:
    """从特征向量计算偏好匹配分（内联版，避免循环导入）。"""
    import json

    config_path = _PROJECT_ROOT / "config" / "weight_config.json"
    hour = datetime.now().hour
    local_hour = (hour + 8) % 24

    if local_hour >= 7 and local_hour < 9:
        slot = "morning"
    elif local_hour >= 9 and local_hour < 18:
        slot = "daytime"
    elif local_hour >= 18 and local_hour < 22:
        slot = "evening"
    else:
        slot = "midnight"

    weights = {k: 1.0 for k in FEATURE_KEYS}
    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            slot_cfg = cfg.get("slots", {}).get(slot, {})
            weights = slot_cfg.get("weights", weights)
    except Exception:
        pass

    total_weighted = 0.0
    total_weights = 0.0
    for key in FEATURE_KEYS:
        feat_val = features.get(key, 50.0)
        w = weights.get(key, 1.0)
        total_weighted += feat_val * w
        total_weights += w

    if total_weights == 0:
        return 50
    return max(0, min(100, int(round(total_weighted / total_weights))))
