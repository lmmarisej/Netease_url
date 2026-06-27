"""
collection_api.py — 自定义音乐集合 API
========================================
SQLite 持久化 + 雷达聚合 + CRUD。

API:
  GET    /api/v3/collections              — 列出用户集合
  POST   /api/v3/collections              — 创建集合
  DELETE /api/v3/collections/<id>         — 删除集合
  POST   /api/v3/collections/<id>/tracks  — 添加歌曲
  DELETE /api/v3/collections/<id>/tracks/<track_id> — 移除歌曲
  GET    /api/v3/collections/<id>/radar   — 10 维雷达数据
  POST   /api/v3/playlist/analyze         — 歌单图谱解析
  GET    /api/v3/playlist/analyses        — 列出已解析歌单
  GET    /api/v3/playlist/analysis/<pid>  — 获取歌单分析结果

数据表（在 music_vault.db 中）:
  - collections(id, user_id, name, created_at)
  - collection_tracks(id, collection_id, track_id, title, artist, added_at)
  - playlist_analyses(playlist_id, user_id, name, cover_url, track_count, radar_json, created_at)
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 项目根 ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = str(_PROJECT_ROOT / "config" / "music_vault.db")

# 10 维特征 key
FEATURE_KEYS = [
    "tempo", "energy", "brightness", "contrast",
    "sub_bass", "vocal", "sentiment",
    "ambiance", "instrumental", "cultural",
]


# ═══════════════════════════════════════════════════════════════
#  数据库初始化
# ═══════════════════════════════════════════════════════════════

def _init_collection_tables() -> None:
    """创建集合相关表（幂等）"""
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'admin',
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                track_id TEXT NOT NULL,
                title TEXT DEFAULT '',
                artist TEXT DEFAULT '',
                added_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                UNIQUE(collection_id, track_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_analyses (
                playlist_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'admin',
                name TEXT DEFAULT '',
                cover_url TEXT DEFAULT '',
                track_count INTEGER DEFAULT 0,
                radar_json TEXT DEFAULT '',
                top_tracks_json TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[collection_api] 建表失败: {e}")


_init_collection_tables()


# ═══════════════════════════════════════════════════════════════
#  集合 CRUD
# ═══════════════════════════════════════════════════════════════

def _get_username() -> str:
    try:
        from auth import get_current_user
        u = get_current_user()
        return u if u else "admin"
    except Exception:
        return "admin"


def list_collections() -> List[Dict[str, Any]]:
    username = _get_username()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, created_at, "
        "(SELECT COUNT(*) FROM collection_tracks WHERE collection_id = collections.id) AS track_count "
        "FROM collections WHERE user_id = ? ORDER BY created_at DESC",
        (username,),
    ).fetchall()

    # 为每个集合取回所有 track_id
    result = []
    for r in rows:
        cid = r["id"]
        tids = conn.execute(
            "SELECT track_id FROM collection_tracks WHERE collection_id = ?", (cid,)
        ).fetchall()
        result.append({
            "id": cid,
            "name": r["name"],
            "track_count": r["track_count"],
            "created_at": r["created_at"],
            "track_ids": [t["track_id"] for t in tids],
        })
    conn.close()
    return result


def create_collection(name: str) -> Dict[str, Any]:
    username = _get_username()
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.execute(
        "INSERT INTO collections (user_id, name) VALUES (?, ?)",
        (username, name.strip()),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": cid, "name": name.strip(), "track_count": 0}


def delete_collection(collection_id: int) -> bool:
    username = _get_username()
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.execute(
        "DELETE FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, username),
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def add_track_to_collection(collection_id: int, track_id: str, title: str = "", artist: str = "") -> bool:
    username = _get_username()
    conn = sqlite3.connect(_DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO collection_tracks (collection_id, track_id, title, artist) VALUES (?, ?, ?, ?)",
            (collection_id, str(track_id), title, artist),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def remove_track_from_collection(collection_id: int, track_id: str) -> bool:
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.execute(
        "DELETE FROM collection_tracks WHERE collection_id = ? AND track_id = ?",
        (collection_id, str(track_id)),
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_collection_tracks(collection_id: int) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT track_id, title, artist FROM collection_tracks WHERE collection_id = ? ORDER BY added_at DESC",
        (collection_id,),
    ).fetchall()
    conn.close()
    return [{"track_id": r["track_id"], "title": r["title"], "artist": r["artist"]} for r in rows]


def get_collection_track_ids(collection_id: int) -> List[str]:
    conn = sqlite3.connect(_DB_PATH)
    rows = conn.execute(
        "SELECT track_id FROM collection_tracks WHERE collection_id = ?",
        (collection_id,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ═══════════════════════════════════════════════════════════════
#  雷达聚合
# ═══════════════════════════════════════════════════════════════

def _get_local_features_for_track(title: str, artist: str) -> Optional[Dict[str, float]]:
    """在本地特征库中按歌名+歌手匹配 10 维特征"""
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row

        # 精确匹配
        row = conn.execute(
            "SELECT m.id FROM music_tracks m "
            "INNER JOIN track_audio_features f ON f.track_id = m.id "
            "WHERE m.title = ? AND m.artist = ? LIMIT 1",
            (title, artist),
        ).fetchone()

        if not row:
            # 模糊匹配
            row = conn.execute(
                "SELECT m.id FROM music_tracks m "
                "INNER JOIN track_audio_features f ON f.track_id = m.id "
                "WHERE m.title LIKE ? OR m.artist LIKE ? LIMIT 1",
                (f"%{title}%", f"%{artist}%"),
            ).fetchone()

        if not row:
            conn.close()
            return None

        track_id = row["id"]
        feats = conn.execute("SELECT * FROM track_audio_features WHERE track_id = ?", (track_id,)).fetchone()
        tags = conn.execute("SELECT tag_name, confidence, category FROM track_tags WHERE track_id = ?", (track_id,)).fetchall()
        conn.close()

        return _build_feature_vector(feats, tags)
    except Exception:
        return None


def _build_feature_vector(feats, tags) -> Dict[str, float]:
    """将 DB 字段映射为 10 维向量 (0-100)"""
    # 安全取值：sqlite3.Row 不支持 .get()，用 keys 检查
    def _safe(column: str, default: float = 50.0) -> float:
        if feats and column in feats.keys():
            return float(feats[column] or default)
        return default

    vec: Dict[str, float] = {}
    vec["tempo"] = _safe("score_tempo")
    vec["energy"] = _safe("score_energy")
    vec["brightness"] = _safe("score_brightness")
    vec["contrast"] = _safe("score_energy_contrast")
    vec["sub_bass"] = _safe("score_sub_bass")
    vec["vocal"] = _safe("score_vocal_dominant")
    vec["sentiment"] = _safe("score_lyric_sentiment")
    vec["ambiance"] = _safe("score_ambiance", 50)  # 无直接列，从标签推算
    vec["instrumental"] = _safe("score_instrumental", 50)
    vec["cultural"] = _safe("score_cultural", 50)

    # PANNs 标签 → electronic_score / rock_score / acousticness / instrument_pureness
    electronic_kw = ["electronic", "edm", "synth", "house", "techno", "trance", "dubstep"]
    rock_kw = ["rock", "metal", "punk", "alternative", "grunge"]
    acoustic_kw = ["acoustic", "folk", "classical", "orchestral", "piano", "guitar"]
    instrumental_kw = ["instrumental", "no vocals", "orchestral", "ambient", "classical"]

    if tags:
        electronic_conf = sum(float(t["confidence"]) for t in tags if t["tag_name"].lower() in electronic_kw)
        rock_conf = sum(float(t["confidence"]) for t in tags if t["tag_name"].lower() in rock_kw)
        acoustic_conf = sum(float(t["confidence"]) for t in tags if t["tag_name"].lower() in acoustic_kw)
        instr_conf = sum(float(t["confidence"]) for t in tags if t["tag_name"].lower() in instrumental_kw)

        vec["electronic_score"] = min(100, electronic_conf * 100)
        vec["rock_score"] = min(100, rock_conf * 100)
        vec["acousticness"] = min(100, acoustic_conf * 100)
        vec["instrument_pureness"] = min(100, instr_conf * 100)

    # LLM 标签 → midnight_emo / guofeng_vibe
    if tags:
        emo_kw = ["失恋", "孤独", "暗黑", "悲伤", "emo", "忧郁", "深夜"]
        guofeng_kw = ["国风", "古韵", "中国风", "民族", "传统"]
        emo_conf = sum(float(t["confidence"]) for t in tags if t["tag_name"] in emo_kw)
        gf_conf = sum(float(t["confidence"]) for t in tags if t["tag_name"] in guofeng_kw)
        vec["midnight_emo"] = min(100, emo_conf * 100)
        vec["guofeng_vibe"] = min(100, gf_conf * 100)

    # 填充缺失 key
    for k in FEATURE_KEYS:
        if k not in vec:
            vec[k] = 50.0

    return vec


def _get_liked_radar_default() -> Dict[str, Any]:
    """回退：从现有 taste-radar API 拉取数据"""
    try:
        from playback_api import _load_netease_cookies
        cookies = _load_netease_cookies()
        username = _get_username()

        # 尝试从 music_vault 聚合已分析歌曲
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT m.title, m.artist FROM music_tracks m "
            "INNER JOIN track_audio_features f ON f.track_id = m.id "
            "LIMIT 50"
        ).fetchall()
        conn.close()

        if rows:
            return _compute_radar_from_tracks(
                [{"title": r["title"], "artist": r["artist"]} for r in rows]
            )
    except Exception:
        pass

    # 返回空雷达
    return {
        "radar": [50] * 10,
        "count": 0,
        "top_tracks": [],
    }


def _compute_radar_from_tracks(tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """对一批 {title, artist} 聚合 10 维雷达"""
    all_feats: List[Dict[str, float]] = []
    top_tracks: List[Dict[str, Any]] = []

    for t in tracks:
        feats = _get_local_features_for_track(t.get("title", ""), t.get("artist", ""))
        if feats:
            all_feats.append(feats)
            top_tracks.append(t)

    count = len(all_feats)
    if count == 0:
        return {"radar": [50] * 10, "count": 0, "top_tracks": []}

    # 取平均
    avg = {}
    for k in FEATURE_KEYS:
        avg[k] = sum(f[k] for f in all_feats) / count

    return {
        "radar": [round(avg.get(k, 50), 1) for k in FEATURE_KEYS],
        "count": count,
        "top_tracks": top_tracks[:3],
    }


def get_collection_radar(collection_id: int) -> Optional[Dict[str, Any]]:
    tracks = get_collection_tracks(collection_id)
    if not tracks:
        return None

    # ── 分离已分析 / 未分析 ──
    matched: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    for t in tracks:
        feats = _get_local_features_for_track(t.get("title", ""), t.get("artist", ""))
        if feats:
            matched.append(t)
        else:
            unmatched.append(t)

    # ── 后台自动下载 + 分析未匹配歌曲 ──
    if unmatched:
        _launch_background_analysis(unmatched)

    # ── 用已分析歌曲计算雷达 ──
    radar = _compute_radar_from_tracks(matched)
    radar["total_tracks"] = len(tracks)
    radar["pending_count"] = len(unmatched)
    return radar


# ═══════════════════════════════════════════════════════════════
#  后台自动下载 + 分析（复用现有管线）
# ═══════════════════════════════════════════════════════════════

# 正在后台分析的 track 集合（防止重复调度）
_pending_analysis: set = set()
_pending_lock = threading.Lock()


def _launch_background_analysis(tracks: List[Dict[str, Any]]) -> None:
    """为未分析歌曲启动后台下载+评分线程（全局去重）"""
    with _pending_lock:
        new_tracks = [t for t in tracks if t["track_id"] not in _pending_analysis]
        for t in new_tracks:
            _pending_analysis.add(t["track_id"])

    if not new_tracks:
        return

    def _worker() -> None:
        for t in new_tracks:
            try:
                _download_and_score_single(t["track_id"], t["title"], t["artist"])
            except Exception as e:
                print(f"[collection_api] 后台分析失败 {t['title']}: {e}")
            finally:
                with _pending_lock:
                    _pending_analysis.discard(t["track_id"])

    t = threading.Thread(target=_worker, daemon=True, name="collection-analysis")
    t.start()


def _download_and_score_single(track_id: str, title: str, artist: str) -> bool:
    """
    下载 + 分析单首歌曲。如果 DB 中已有本地文件则直接复用，不重复下载。

    Returns:
        True 表示分析完成并已写入 DB
    """
    try:
        from music_api import url_v1
        from music_downloader import MusicDownloader
        from services.song_storage import SongStorageService
        from music_processor.single_scorer import score_single_track
        from playback_api import _load_netease_cookies
    except ImportError as e:
        print(f"[collection_api] 导入依赖失败: {e}")
        return False

    username = _get_username()

    # ── 优先检查 DB 中是否已有本地文件 ──
    existing_path = _find_local_file_for_track(title, artist)
    if existing_path:
        print(f"[collection_api] 复用本地文件: {title} -> {existing_path}")
        try:
            score_result = score_single_track(
                file_path=existing_path,
                title=title, artist=artist, album="",
                username=username,
            )
            print(f"[collection_api] 打分完成(复用): {title}, pref_score={score_result.get('preference_score', 0)}")
            return True
        except Exception as e:
            print(f"[collection_api] 打分失败(复用) {title}: {e}")
            return False

    # ── 无本地文件，从网易云下载 ──
    cookies = _load_netease_cookies()
    if not cookies:
        print(f"[collection_api] 无有效 Cookie，无法下载 {title}")
        return False

    try:
        # Step 1: 获取下载链接
        url_resp = url_v1(track_id, "exhigh", cookies)
        if not url_resp:
            print(f"[collection_api] 无法获取下载链接: {title}")
            return False
        download_url = url_resp.get("data", [{}])[0].get("url", "")
        if not download_url:
            print(f"[collection_api] 下载链接为空: {title}")
            return False

        # Step 2: CAS 下载存储
        storage = SongStorageService()
        store_path, content_hash = storage.download_and_store(
            username=username,
            download_url=download_url,
            metadata={"title": title, "artist": artist, "ext": "mp3"},
        )
        print(f"[collection_api] CAS 存储完成: {title} -> {store_path}")

        # Step 3: 自动打分
        try:
            score_result = score_single_track(
                file_path=str(store_path),
                title=title, artist=artist, album="",
                username=username,
            )
            print(f"[collection_api] 打分完成: {title}, pref_score={score_result.get('preference_score', 0)}")
        except Exception as e:
            print(f"[collection_api] 打分失败 {title}: {e}")
            return False

        return True

    except Exception as e:
        print(f"[collection_api] 下载分析异常 {title}: {e}")
        return False


def _find_local_file_for_track(title: str, artist: str) -> Optional[str]:
    """在 music_tracks 中查找已有本地文件路径（按歌名+歌手模糊匹配）"""
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        # 先精确匹配
        row = conn.execute(
            "SELECT file_path FROM music_tracks WHERE title = ? AND artist = ? AND file_path IS NOT NULL AND file_path != '' LIMIT 1",
            (title, artist),
        ).fetchone()
        if not row:
            # 模糊匹配
            row = conn.execute(
                "SELECT file_path FROM music_tracks WHERE title LIKE ? AND artist LIKE ? AND file_path IS NOT NULL AND file_path != '' LIMIT 1",
                (f"%{title}%", f"%{artist}%"),
            ).fetchone()
        conn.close()
        if row and row["file_path"] and Path(row["file_path"]).exists():
            return row["file_path"]
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  歌单解析
# ═══════════════════════════════════════════════════════════════

def analyze_playlist(playlist_id: str) -> Dict[str, Any]:
    """拉取歌单 → 聚合特征 → 存储结果"""
    try:
        from music_api import playlist_detail
        from playback_api import _load_netease_cookies
    except ImportError:
        return {"error": "无法导入 music_api"}

    cookies = _load_netease_cookies()
    if not cookies:
        return {"error": "未配置 Cookie"}

    try:
        pid = int(playlist_id)
    except ValueError:
        return {"error": "无效的歌单 ID"}

    try:
        info = playlist_detail(pid, cookies)
    except Exception as e:
        return {"error": f"获取歌单失败: {e}"}

    name = info.get("name", f"歌单 {pid}")
    cover_url = info.get("coverImgUrl", "")
    raw_tracks = info.get("tracks", [])

    tracks = [
        {
            "title": t.get("name", ""),
            "artist": "/".join(a.get("name", "") for a in t.get("ar", [])),
        }
        for t in raw_tracks
    ]

    radar = _compute_radar_from_tracks(tracks)

    # 持久化
    username = _get_username()
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO playlist_analyses (playlist_id, user_id, name, cover_url, track_count, radar_json, top_tracks_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(pid), username, name, cover_url,
            len(tracks),
            json.dumps(radar, ensure_ascii=False),
            json.dumps(radar.get("top_tracks", []), ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "playlist_id": str(pid),
        "name": name,
        "cover_url": cover_url,
        "track_count": len(tracks),
        "radar": radar["radar"],
        "count": radar["count"],
        "top_tracks": radar["top_tracks"],
    }


def list_playlist_analyses() -> List[Dict[str, Any]]:
    username = _get_username()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT playlist_id, name, cover_url, track_count, radar_json, top_tracks_json, created_at "
        "FROM playlist_analyses WHERE user_id = ? ORDER BY created_at DESC",
        (username,),
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        try:
            radar_data = json.loads(r["radar_json"] or "{}")
            top_tracks = json.loads(r["top_tracks_json"] or "[]")
        except Exception:
            radar_data = {}
            top_tracks = []

        result.append({
            "playlist_id": r["playlist_id"],
            "name": r["name"],
            "cover_url": r["cover_url"],
            "track_count": r["track_count"],
            "radar": radar_data.get("radar", [50] * 10) if isinstance(radar_data, dict) else [50] * 10,
            "count": radar_data.get("count", 0) if isinstance(radar_data, dict) else 0,
            "top_tracks": top_tracks[:3],
            "created_at": r["created_at"],
        })
    return result


def get_playlist_analysis(playlist_id: str) -> Optional[Dict[str, Any]]:
    username = _get_username()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM playlist_analyses WHERE playlist_id = ? AND user_id = ?",
        (playlist_id, username),
    ).fetchone()
    conn.close()

    if not row:
        return None

    try:
        radar_data = json.loads(row["radar_json"] or "{}")
        top_tracks = json.loads(row["top_tracks_json"] or "[]")
    except Exception:
        radar_data = {}
        top_tracks = []

    return {
        "playlist_id": row["playlist_id"],
        "name": row["name"],
        "cover_url": row["cover_url"],
        "track_count": row["track_count"],
        "radar": radar_data.get("radar", [50] * 10) if isinstance(radar_data, dict) else [50] * 10,
        "count": radar_data.get("count", 0) if isinstance(radar_data, dict) else 0,
        "top_tracks": top_tracks[:3],
        "created_at": row["created_at"],
    }


# ═══════════════════════════════════════════════════════════════
#  Flask 路由注册
# ═══════════════════════════════════════════════════════════════

def register_collection_routes(app):
    """在 Flask app 上注册集合相关路由"""
    from flask import request

    @app.route("/api/v3/collections", methods=["GET"])
    def api_list_collections():
        try:
            result = list_collections()
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/collections", methods=["POST"])
    def api_create_collection():
        try:
            data = request.get_json(silent=True) or {}
            name = data.get("name", "").strip()
            if not name:
                return {"success": False, "message": "集合名称不能为空"}, 400
            result = create_collection(name)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/collections/<int:collection_id>", methods=["DELETE"])
    def api_delete_collection(collection_id):
        try:
            ok = delete_collection(collection_id)
            if ok:
                return {"success": True, "message": "已删除"}
            return {"success": False, "message": "集合不存在"}, 404
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/collections/<int:collection_id>/tracks", methods=["POST"])
    def api_add_track(collection_id):
        try:
            data = request.get_json(silent=True) or {}
            track_id = data.get("track_id", "")
            title = data.get("title", "")
            artist = data.get("artist", "")
            if not track_id:
                return {"success": False, "message": "track_id 不能为空"}, 400
            ok = add_track_to_collection(collection_id, track_id, title, artist)
            return {"success": True, "message": "已添加" if ok else "已存在"}
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/collections/<int:collection_id>/tracks/<track_id>", methods=["DELETE"])
    def api_remove_track(collection_id, track_id):
        try:
            ok = remove_track_from_collection(collection_id, track_id)
            if ok:
                return {"success": True, "message": "已移除"}
            return {"success": False, "message": "歌曲不在集合中"}, 404
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/collections/<int:collection_id>/radar", methods=["GET"])
    def api_collection_radar(collection_id):
        try:
            radar = get_collection_radar(collection_id)
            if radar is None:
                return {"success": False, "message": "集合为空或不存在"}, 404
            return {"success": True, "data": radar}
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/playlist/analyze", methods=["POST"])
    def api_analyze_playlist():
        try:
            data = request.get_json(silent=True) or {}
            playlist_id = data.get("playlist_id", "").strip()
            if not playlist_id:
                return {"success": False, "message": "请输入歌单 ID"}, 400
            result = analyze_playlist(playlist_id)
            if "error" in result:
                return {"success": False, "message": result["error"]}, 400
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/playlist/analyses", methods=["GET"])
    def api_list_analyses():
        try:
            result = list_playlist_analyses()
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    @app.route("/api/v3/playlist/analysis/<playlist_id>", methods=["GET"])
    def api_get_analysis(playlist_id):
        try:
            result = get_playlist_analysis(playlist_id)
            if result is None:
                return {"success": False, "message": "未找到该歌单分析"}, 404
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}, 500

    # 需要导入 request
    from flask import request
