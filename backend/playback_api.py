"""
播放历史与推荐源 API (v3)
===========================
FastAPI APIRouter，提供播放行为记录、历史查询、歌曲推荐接口。

依赖：
    - SQLAlchemy 2.0+（ORM + Core）
    - SQLite（与项目现有 sqlite3 共享 config/music_vault.db）

注册方式（在 fastapi_app.py 中）：
    from playback_api import router as playback_router
    app.include_router(playback_router)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    declarative_base,
    sessionmaker,
)

# ────────────────────────── 日志 ──────────────────────────
logger = logging.getLogger("playback_api")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

# ────────────────────────── 路径 & 数据库 ──────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = str(_PROJECT_ROOT / "config" / "music_vault.db")
_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 多线程支持
    echo=False,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base: DeclarativeBase = declarative_base()

router = APIRouter(prefix="/api/v3/music", tags=["播放历史与推荐"])

# ────────────────────────── Pydantic 请求/响应模型 ──────────────────────────


class PlayLogRequest(BaseModel):
    """前端上报的听歌行为"""

    track_id: str = Field(..., min_length=1, description="歌曲唯一 ID")
    title: str = Field(default="", description="歌曲名")
    artist: str = Field(default="", description="歌手名")
    play_duration: float = Field(..., ge=0, description="实际播放秒数")
    total_duration: float = Field(default=0, ge=0, description="歌曲总秒数")
    source_type: Optional[str] = Field(default=None, description="推荐来源: hot_list / custom_playlist")


class PlayHistoryItem(BaseModel):
    """播放历史列表单项"""

    id: int
    track_id: str
    title: str
    artist: str
    play_duration: float
    total_duration: float
    is_skipped: bool
    timestamp: str


class PlayHistoryResponse(BaseModel):
    """播放历史分页响应"""

    total: int
    page: int
    page_size: int
    items: List[PlayHistoryItem]


class RecommendTrack(BaseModel):
    """推荐歌曲（含完整特征向量 + 偏好打分 + 来源标注）"""

    track_id: str
    title: str
    artist: str
    album: str = ""
    cover_url: str = ""
    bpm: float = 0.0
    vocal_ratio: float = 0.0
    energy: float = 0.0
    danceability: float = 0.0
    acousticness: float = 0.0
    instrumentalness: float = 0.0
    valence: float = 0.0
    source_label: str = ""  # "网易云热榜" / "自定义歌单"
    source: str = "netease"  # "local" | "netease" — 歌曲来源
    preference_score: int = 0  # 0-100 用户偏好匹配分
    file_path: str = ""  # 本地文件路径（local 歌曲）


class RecommendResponse(BaseModel):
    """推荐接口响应（分页）"""

    total: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    source_type: str
    source_label: str
    generated_at: str
    tracks: List[RecommendTrack]


# ────────────────────────── SQLAlchemy 数据模型 ──────────────────────────


class PlaybackLog(Base):
    """
    播放行为日志表。

    存储每次播放的核心行为数据，用于：
    1. 构建用户听歌画像（长周期偏好分析）
    2. 跳过率分析 → 调整推荐算法权重
    3. 播放完成率 → 衡量推荐质量
    """

    __tablename__ = "playback_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True, comment="用户名")
    track_id = Column(String(128), nullable=False, index=True, comment="歌曲唯一 ID")
    title = Column(String(256), default="", comment="歌曲名")
    artist = Column(String(256), default="", comment="歌手名")
    play_duration = Column(Float, nullable=False, default=0.0, comment="实际播放秒数")
    total_duration = Column(Float, nullable=False, default=0.0, comment="歌曲总秒数")
    is_skipped = Column(Boolean, default=False, index=True, comment="是否跳过（播放比例 < 20%）")
    source_type = Column(String(32), default="", comment="推荐来源：hot_list / custom_playlist / manual")
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="播放时间（UTC）",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "track_id": self.track_id,
            "title": self.title,
            "artist": self.artist,
            "play_duration": self.play_duration,
            "total_duration": self.total_duration,
            "is_skipped": self.is_skipped,
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
        }


# ────────────────────────── 数据库初始化 ──────────────────────────


def init_db() -> None:
    """创建所有缺失的表（幂等操作，已存在的表不重复创建）"""
    Base.metadata.create_all(bind=engine)
    logger.info(f"数据库表初始化完成: {_DB_PATH}")


# 模块导入时自动建表
init_db()


# ────────────────────────── 依赖注入：数据库会话 ──────────────────────────


def get_db() -> Session:
    """FastAPI 依赖注入：获取数据库会话，请求结束后自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ────────────────────────── API 端点 ──────────────────────────


@router.post("/log", response_model=Dict[str, Any])
async def log_playback(req: PlayLogRequest, db: Session = Depends(get_db)) -> JSONResponse:
    """
    记录单次播放行为。

    规则：
    - 若 play_duration / total_duration < 0.2，自动标记 is_skipped = True
    - 若 total_duration 为 0，跳过率计算回退为 0（不标记跳过）

    返回：
        200: {"success": True, "data": {"id": <新记录ID>, "is_skipped": bool}}
    """
    # ── 跳过判定 ──
    skip_ratio = 0.0
    is_skipped = False
    if req.total_duration > 0:
        skip_ratio = req.play_duration / req.total_duration
        is_skipped = skip_ratio < 0.2  # 播放不足 20% 视为跳过

    # ── 构造 ORM 对象 ──
    log_entry = PlaybackLog(
        user_id="current_user",  # TODO: 接入真实认证后替换为 req.user_id
        track_id=req.track_id,
        title=req.title,
        artist=req.artist,
        play_duration=req.play_duration,
        total_duration=req.total_duration,
        is_skipped=is_skipped,
        source_type=req.source_type or "",
        timestamp=datetime.now(timezone.utc),
    )

    # ── 事务写入 ──
    try:
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        logger.info(
            f"播放记录已写入: track={req.track_id}, "
            f"played={req.play_duration:.1f}s/{req.total_duration:.1f}s, "
            f"skipped={is_skipped}, ratio={skip_ratio:.2f}"
        )
        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "id": log_entry.id,
                    "is_skipped": is_skipped,
                    "skip_ratio": round(skip_ratio, 3),
                },
            }
        )
    except Exception as e:
        db.rollback()
        logger.error(f"写入播放记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {e}")


@router.get("/history", response_model=PlayHistoryResponse)
async def get_history(
    page: int = Query(default=1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
) -> PlayHistoryResponse:
    """
    分页返回当前用户的听歌历史。

    排序规则：按 timestamp 降序（最近播放在前）。
    当前版本 user_id 固定为 "current_user"，后续接入认证后自动切换。
    """
    user_id = "current_user"  # TODO: 接入真实认证

    # ── 总数 ──
    total = (
        db.query(PlaybackLog)
        .filter(PlaybackLog.user_id == user_id)
        .count()
    )

    # ── 分页查询 ──
    offset = (page - 1) * page_size
    rows = (
        db.query(PlaybackLog)
        .filter(PlaybackLog.user_id == user_id)
        .order_by(PlaybackLog.timestamp.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return PlayHistoryResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[PlayHistoryItem(**row.to_dict()) for row in rows],
    )


@router.get("/recommend", response_model=RecommendResponse)
async def get_recommend(
    source_type: str = Query(
        default="hot_list",
        description="推荐来源: hot_list | custom_playlist | local_library",
    ),
    playlist_id: Optional[str] = Query(
        default=None,
        description="自定义歌单 ID（source_type=custom_playlist 时必填）",
    ),
    sort_order: str = Query(
        default="desc",
        description="偏好分排序: desc（高分优先）| asc（低分优先）",
    ),
    page: int = Query(
        default=1, ge=1,
        description="页码（从 1 开始）",
    ),
    page_size: int = Query(
        default=50, ge=1, le=200,
        description="每页条数",
    ),
) -> RecommendResponse:
    """
    核心推荐接口。

    - hot_list: 网易云热榜（仅热榜歌曲，本地有则自动匹配特征）
    - custom_playlist: 自定义歌单（仅歌单歌曲，本地有则自动匹配特征）
    - local_library: 本地音乐库（仅本地已分析歌曲）

    后台增强：未匹配的在线歌曲异步下载 → CAS → 打分 → 下次带特征
    支持 sort_order=asc/desc 按偏好分排序
    """
    # ── 参数校验 ──
    if source_type not in ("hot_list", "custom_playlist", "local_library"):
        raise HTTPException(
            status_code=400,
            detail="source_type 仅支持 hot_list / custom_playlist / local_library",
        )

    if source_type == "custom_playlist" and not playlist_id:
        raise HTTPException(
            status_code=400,
            detail="source_type=custom_playlist 时必须提供 playlist_id",
        )

    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    # ── 用户信息 ──
    username = "admin"
    try:
        from auth import get_current_user
        u = get_current_user()
        if u:
            username = u
    except ImportError:
        pass

    # ══════════ 分支：本地音乐库 ══════════
    if source_type == "local_library":
        local_tracks = _get_local_top_tracks(username, limit=50)
        tracks = _build_recommend_tracks(
            [], source_type, "本地音乐库",
            local_tracks=local_tracks,
        )
        tracks = _sort_tracks_by_preference(tracks, sort_order)
        total = len(tracks)
        total_pages = max(1, (total + page_size - 1) // page_size)
        paged = tracks[(page - 1) * page_size : page * page_size]
        return RecommendResponse(
            total=total, page=page, page_size=page_size, total_pages=total_pages,
            source_type=source_type,
            source_label="本地音乐库",
            generated_at=datetime.now(timezone.utc).isoformat(),
            tracks=paged,
        )

    # ══════════ 分支：网易云热榜 / 自定义歌单 ══════════
    cookies = _load_netease_cookies()
    raw_tracks: List[Dict[str, Any]] = []
    playlist_name = ""

    if cookies:
        pid = int(playlist_id) if playlist_id else _HOT_CHART_ID
        try:
            from music_api import playlist_detail, APIException as NeteaseAPIError

            playlist_info = playlist_detail(pid, cookies)
            raw_tracks = playlist_info.get("tracks", [])
            playlist_name = playlist_info.get("name", "网易云热榜" if source_type == "hot_list" else "")
        except (NeteaseAPIError, ImportError, Exception) as e:
            logger.warning(f"网易云 API 调用失败: {e}")
    else:
        logger.warning("无有效网易云 Cookie")

    # ── 仅网易云歌单歌曲，local_tracks=None（不混入纯本地歌曲） ──
    #   但 _get_local_features 仍会匹配已在本地库的热榜歌曲 → 带特征
    tracks = _build_recommend_tracks(
        raw_tracks, source_type,
        playlist_name or "网易云热榜",
        local_tracks=None,
    )

    # ── 排序 ──
    tracks = _sort_tracks_by_preference(tracks, sort_order)

    # ── 分页 ──
    total = len(tracks)
    total_pages = max(1, (total + page_size - 1) // page_size)
    paged = tracks[(page - 1) * page_size : page * page_size]

    # ── 后台预下载未匹配歌曲 ──
    netease_unmatched = [t for t in tracks if t.source == "netease" and t.bpm < 0]
    if netease_unmatched:
        _async_download_and_score(netease_unmatched, cookies, username)

    return RecommendResponse(
        total=total, page=page, page_size=page_size, total_pages=total_pages,
        source_type=source_type,
        source_label=playlist_name or "网易云热榜",
        generated_at=datetime.now(timezone.utc).isoformat(),
        tracks=paged,
    )

    # ── Step 4: 按 preference_score 排序 ──
    tracks = _sort_tracks_by_preference(tracks, sort_order)

    # ── Step 5: 后台预下载 + 打分（未匹配的在线歌曲，下次变本地） ──
    netease_unmatched = [t for t in tracks if t.source == "netease" and t.bpm < 0]
    if netease_unmatched:
        _async_download_and_score(netease_unmatched, cookies, username)

    return RecommendResponse(
        total=len(tracks),
        source_type=source_type,
        source_label=playlist_name or ("本地音乐库" if not cookies else "网易云热榜"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        tracks=tracks,
    )


# ══════════════════════════════════════════════════════════════════════
#  偏好打分 — 基于时段权重的加权求和
# ══════════════════════════════════════════════════════════════════════

# 10 维特征 key 列表（与 weight_config.json 对齐）
FEATURE_KEYS = [
    "tempo", "energy", "vocal_ratio", "bass_intensity", "acousticness",
    "electronic_score", "rock_score", "instrument_pureness",
    "midnight_emo", "guofeng_vibe",
]

# 时段 → 小时范围映射
SLOT_HOUR_RANGES: Dict[str, tuple] = {
    "morning":  (7, 9),    # [7, 9)
    "daytime":  (9, 18),   # [9, 18)
    "evening":  (18, 22),  # [18, 22)
    "midnight": (22, 7),   # [22, 24) U [0, 7)
}


def _get_current_slot() -> str:
    """根据当前小时返回时段 slot key"""
    hour = datetime.now(timezone.utc).hour
    # 假设 UTC+8（中国时区）
    local_hour = (hour + 8) % 24
    for slot, (start, end) in SLOT_HOUR_RANGES.items():
        if slot == "midnight":
            if local_hour >= start or local_hour < end:
                return slot
        elif start <= local_hour < end:
            return slot
    return "daytime"


def _load_weight_config() -> Dict[str, Any]:
    """加载 weight_config.json，失败时回退默认"""
    config_path = _PROJECT_ROOT / "config" / "weight_config.json"
    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"加载权重配置失败: {e}")
    # 默认回退
    return {
        "slots": {
            "morning": {"weights": {k: 1.0 for k in FEATURE_KEYS}},
            "daytime": {"weights": {k: 1.0 for k in FEATURE_KEYS}},
            "evening": {"weights": {k: 1.0 for k in FEATURE_KEYS}},
            "midnight": {"weights": {k: 1.0 for k in FEATURE_KEYS}},
        }
    }


def compute_preference_score(
    track_features: Dict[str, float],
    slot: Optional[str] = None,
) -> int:
    """
    基于时段权重计算用户偏好匹配分 (0-100)。

    score = Σ (feature_i × weight_i) / Σ weight_i

    Args:
        track_features: 10 维特征向量
        slot: 时段 key，None 则自动选择

    Returns:
        0-100 整数偏好分
    """
    import json as _json

    if slot is None:
        slot = _get_current_slot()

    config = _load_weight_config()
    slots = config.get("slots", {})
    slot_config = slots.get(slot, {})
    weights = slot_config.get("weights", {})

    if not weights:
        return 50

    total_weighted = 0.0
    total_weights = 0.0

    for key in FEATURE_KEYS:
        feat_val = track_features.get(key, 50.0)
        w = weights.get(key, 1.0)
        total_weighted += feat_val * w
        total_weights += w

    if total_weights == 0:
        return 50

    raw_score = total_weighted / total_weights
    # 钳制到 0-100
    return max(0, min(100, int(round(raw_score))))


# ══════════════════════════════════════════════════════════════════════
#  本地优先推荐 — 从 music_vault.db 拉取已分析歌曲
# ══════════════════════════════════════════════════════════════════════


def _get_local_top_tracks(
    username: str = "admin",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    从本地 music_vault.db 中查询已分析歌曲，按用户偏好排序。

    排序规则：
      1. is_favorite=1 优先
      2. completion_rate DESC
      3. 必须有 track_audio_features（已扫描过）

    Returns:
        [{track_id, title, artist, album, cover_url, file_path,
          features_dict, source="local"}, ...]
    """
    db_path = str(_PROJECT_ROOT / "config" / "music_vault.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        logger.error(f"无法连接本地特征库: {e}")
        return []

    try:
        rows = conn.execute(
            """
            SELECT
                m.id AS track_id,
                m.title,
                m.artist,
                m.album,
                m.file_path,
                COALESCE(ub.is_favorite, 0) AS is_favorite,
                COALESCE(ub.completion_rate, 0) AS completion_rate
            FROM music_tracks m
            INNER JOIN track_audio_features f ON f.track_id = m.id
            LEFT JOIN user_track_behaviors ub
                ON ub.track_id = m.id AND ub.username = ?
            WHERE m.title IS NOT NULL AND m.title != ''
            ORDER BY
                COALESCE(ub.is_favorite, 0) DESC,
                COALESCE(ub.completion_rate, 0) DESC,
                m.id DESC
            LIMIT ?
            """,
            (username, limit),
        ).fetchall()

        result: List[Dict[str, Any]] = []
        for row in rows:
            track_id = row["track_id"]
            # 读取特征
            feats = conn.execute(
                "SELECT * FROM track_audio_features WHERE track_id = ?",
                (track_id,),
            ).fetchone()
            tags = conn.execute(
                "SELECT tag_name, confidence, category FROM track_tags WHERE track_id = ?",
                (track_id,),
            ).fetchall()

            feature_vec = _build_feature_vector(feats, tags)

            result.append({
                "track_id": str(track_id),
                "title": row["title"] or "",
                "artist": row["artist"] or "",
                "album": row["album"] or "",
                "cover_url": "",  # 本地歌曲无封面 URL
                "file_path": row["file_path"] or "",
                "features": feature_vec,
                "source": "local",
                "is_favorite": row["is_favorite"],
                "completion_rate": row["completion_rate"],
            })

        return result

    except Exception as e:
        logger.warning(f"查询本地 Top 歌曲失败: {e}")
        return []
    finally:
        conn.close()

_NETEASE_HOT_CHART_ID = 3778678  # 网易云「云音乐热歌榜」
_HOT_CHART_ID = _NETEASE_HOT_CHART_ID

# ── Cookie 加载 ──


def _load_netease_cookies() -> Dict[str, str]:
    """从用户专属 cookies.json 加载活跃的网易云 Cookie"""
    try:
        from cookie_manager import CookieManager

        # 读取当前用户
        username = "admin"  # 默认用户，后续接入认证后替换
        try:
            from auth import get_current_user
            u = get_current_user()
            if u:
                username = u
        except ImportError:
            pass

        cookie_file = str(_PROJECT_ROOT / "config" / "users" / username / "cookies.json")
        manager = CookieManager(cookie_file)
        cookie_str = manager.read_cookie()
        return manager.parse_cookie_string(cookie_str) if cookie_str else {}
    except Exception as e:
        logger.warning(f"加载 Cookie 失败: {e}")
        return {}


# ── 特征查询 ──


def _get_local_features(title: str, artist: str) -> Optional[Dict[str, float]]:
    """
    在本地 music_vault.db 中按歌名 + 歌手模糊匹配，返回 10 维特征向量。

    匹配逻辑：
    1. music_tracks 表模糊匹配 title 和 artist
    2. 找到后从 track_audio_features 读取声学特征
    3. 从 track_tags 读取 AI 标签并聚合成 10 维向量

    返回 None 表示未在本地特征库中找到该歌曲。
    """
    db_path = str(_PROJECT_ROOT / "config" / "music_vault.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        logger.error(f"无法连接本地特征库: {e}")
        return None

    try:
        # ── Step 1: 模糊匹配歌曲（先精确 title，再 fallback LIKE） ──
        row = conn.execute(
            """
            SELECT m.id, m.title, m.artist
            FROM music_tracks m
            WHERE LOWER(m.title) = LOWER(?)
              AND LOWER(m.artist) LIKE LOWER(?)
            LIMIT 1
            """,
            (title.strip(), f"%{artist.strip()}%"),
        ).fetchone()
        if not row:
            # 宽松匹配：title 包含 + artist 包含
            row = conn.execute(
                """
                SELECT m.id, m.title, m.artist
                FROM music_tracks m
                WHERE LOWER(m.title) LIKE LOWER(?)
                  AND LOWER(m.artist) LIKE LOWER(?)
                LIMIT 1
                """,
                (f"%{title.strip()}%", f"%{artist.strip()}%"),
            ).fetchone()

        if not row:
            return None

        track_id = row["id"]

        # ── Step 2: 读取声学特征 ──
        feats = conn.execute(
            "SELECT * FROM track_audio_features WHERE track_id = ?", (track_id,)
        ).fetchone()

        # ── Step 3: 读取 AI 标签（PANNs + LLM） ──
        tags = conn.execute(
            "SELECT tag_name, confidence, category FROM track_tags WHERE track_id = ?",
            (track_id,),
        ).fetchall()

        return _build_feature_vector(feats, tags)

    except Exception as e:
        logger.warning(f"查询本地特征失败: title={title}, artist={artist}, error={e}")
        return None
    finally:
        conn.close()


def _build_feature_vector(
    feats: Optional[sqlite3.Row],
    tags: List[sqlite3.Row],
) -> Dict[str, float]:
    """
    将 DB 原始字段映射为 10 维推荐特征向量 (0-100 范围)。

    映射规则：
      DB 字段                    → 推荐维度
      ─────────────────────────────────────────────
      score_tempo               → tempo
      score_energy              → energy
      score_vocal_dominant      → vocal_ratio
      score_sub_bass            → bass_intensity
      PANNs: electronic/edm/... → electronic_score
      PANNs: rock/metal/...     → rock_score
      PANNs: acoustic/instrum.. → acousticness
      PANNs: instrumental/...   → instrument_pureness
      LLM:   失恋/孤独/暗黑/... → midnight_emo
      LLM:   国风/古韵/中国风.. → guofeng_vibe
    """
    # ── 声学特征（0-100 直接读取） ──
    if feats:
        tempo = float(feats["score_tempo"] or 50)
        energy = float(feats["score_energy"] or 50)
        vocal_ratio = float(feats["score_vocal_dominant"] or 50)
        bass_intensity = float(feats["score_sub_bass"] or 50)
    else:
        tempo = energy = vocal_ratio = bass_intensity = 50.0

    # ── AI 标签特征（0-100，按标签名聚合） ──
    electronic_score = _tag_score(tags, _ELECTRONIC_TAGS)
    rock_score = _tag_score(tags, _ROCK_TAGS)
    acousticness = _tag_score(tags, _ACOUSTIC_TAGS)
    instrument_pureness = _tag_score(tags, _INSTRUMENTAL_TAGS)
    midnight_emo = _tag_score(tags, _MIDNIGHT_EMO_TAGS)
    guofeng_vibe = _tag_score(tags, _GUOFENG_TAGS)

    return {
        "tempo": round(tempo, 1),
        "energy": round(energy, 1),
        "vocal_ratio": round(vocal_ratio, 1),
        "bass_intensity": round(bass_intensity, 1),
        "acousticness": round(acousticness, 1),
        "electronic_score": round(electronic_score, 1),
        "rock_score": round(rock_score, 1),
        "instrument_pureness": round(instrument_pureness, 1),
        "midnight_emo": round(midnight_emo, 1),
        "guofeng_vibe": round(guofeng_vibe, 1),
    }


def _tag_score(tags: List[sqlite3.Row], match_set: set) -> float:
    """
    从标签列表中聚合匹配标签的置信度，映射到 0-100。

    策略：取匹配标签中置信度最高的值 × 100（PANNs 置信度为 0-1 浮点）。
    LLM 标签无置信度，视为 50。
    """
    best = 0.0
    for t in tags:
        if t["tag_name"].lower() in match_set:
            conf = float(t["confidence"]) if t["confidence"] else 0.5
            # PANNs: 0-1 float → 0-100
            if t["category"] == "panns":
                conf = conf * 100.0
            # LLM: 按匹配数量加权
            else:
                conf = min(conf + 30.0, 95.0) if best > 0 else 55.0
            if conf > best:
                best = conf
    return min(best, 100.0)


# ── 标签映射表（小写匹配） ──

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

# ── 歌曲构建 ──


def _build_recommend_tracks(
    raw_tracks: List[Dict[str, Any]],
    source_type: str,
    playlist_name: str,
    local_tracks: Optional[List[Dict[str, Any]]] = None,
) -> List[RecommendTrack]:
    """
    构建推荐列表 — 本地优先，网易云兜底。

    策略：
      1. 先渲染 local_tracks（已含完整特征向量）→ source="local"
      2. 再遍历 raw_tracks（网易云 API 返回）→ source="netease"
      3. 每条计算 preference_score

    参数：
        raw_tracks: 网易云 API 返回的 tracks 数组
        source_type: "hot_list" | "custom_playlist"
        playlist_name: 歌单名称（用于 source_label）
        local_tracks: 本地音乐库 Top N（来自 _get_local_top_tracks）
    """
    result: List[RecommendTrack] = []
    source_label = playlist_name or ("网易云热榜" if source_type == "hot_list" else "")
    seen_titles: set = set()  # 去重：同名同歌手不重复

    def _add_track(t: Dict[str, Any], src: str, features: Optional[Dict[str, float]] = None) -> bool:
        """添加一条推荐，返回 True 表示新增，False 表示重复跳过"""
        title = t.get("title", "") or t.get("name", "")
        artist = ""
        if "ar" in t:
            artist = ", ".join(ar.get("name", "") for ar in t.get("ar", []))
        else:
            artist = t.get("artist", "") or t.get("artists", "")
        dedup_key = f"{title.strip().lower()}||{artist.strip().lower()}"
        if dedup_key in seen_titles:
            return False
        seen_titles.add(dedup_key)

        # 构建 features
        feats = features or t.get("features")
        if not feats and src == "netease":
            feats = _get_local_features(title, artist)
        if feats:
            bpm = feats.get("tempo", 50.0)
            vocal_ratio = feats.get("vocal_ratio", 50.0)
            energy = feats.get("energy", 50.0)
            acousticness = feats.get("acousticness", 50.0)
            instrumentalness = feats.get("instrument_pureness", 50.0)
            valence = feats.get("midnight_emo", 50.0)
            pref_score = compute_preference_score(feats)
        else:
            bpm = vocal_ratio = energy = acousticness = instrumentalness = valence = -1.0
            pref_score = 0

        album = t.get("album", "") or (t.get("al", {}).get("name", "") if isinstance(t.get("al"), dict) else "")
        cover_url = t.get("cover_url", "") or (t.get("al", {}).get("picUrl", "") if isinstance(t.get("al"), dict) else "")
        track_id = str(t.get("track_id", "") or t.get("id", ""))
        file_path = t.get("file_path", "")

        result.append(RecommendTrack(
            track_id=track_id,
            title=title,
            artist=artist,
            album=album,
            cover_url=cover_url,
            bpm=bpm,
            vocal_ratio=vocal_ratio,
            energy=energy,
            danceability=50.0,
            acousticness=acousticness,
            instrumentalness=instrumentalness,
            valence=valence,
            source_label=source_label,
            source=src,
            preference_score=pref_score,
            file_path=file_path,
        ))
        return True

    # ── Step 1: 本地歌曲优先 ──
    local_count = 0
    if local_tracks:
        for lt in local_tracks:
            if _add_track(lt, "local", lt.get("features")):
                local_count += 1

    # ── Step 2: 网易云兜底 ──
    netease_count = 0
    for t in raw_tracks:
        if _add_track(t, "netease"):
            netease_count += 1

    logger.info(
        f"推荐构建完成: total={len(result)}, "
        f"local={local_count}, netease={netease_count}, "
        f"source={source_label}"
    )
    return result


# ══════════════════════════════════════════════════════════════════════
#  排序 + 后台自动解析网易云歌单
# ══════════════════════════════════════════════════════════════════════


def _sort_tracks_by_preference(
    tracks: List[RecommendTrack],
    sort_order: str = "desc",
) -> List[RecommendTrack]:
    """按 preference_score 排序。desc=高分优先，asc=低分优先。"""
    reverse = sort_order == "desc"
    return sorted(tracks, key=lambda t: t.preference_score, reverse=reverse)


def _async_fetch_netease_playlist(
    playlist_id: int,
    source_type: str,
    username: str = "admin",
) -> None:
    """
    后台线程：拉取网易云歌单 → 下载新歌 → CAS 存储 → 自动打分 → 写入 DB。

    不阻塞推荐响应，处理结果写入 music_vault.db，
    下次刷新时新歌自动以 source=\"local\" 出现在推荐流中。
    """
    import threading

    def _worker() -> None:
        try:
            cookies = _load_netease_cookies()
            if not cookies:
                logger.info("[AsyncPlaylist] 无有效 Cookie，跳过在线歌单拉取")
                return

            # ── 拉取歌单 ──
            from music_api import playlist_detail

            playlist_info = playlist_detail(playlist_id, cookies)
            raw_tracks = playlist_info.get("tracks", [])
            if not raw_tracks:
                logger.info("[AsyncPlaylist] 歌单为空，跳过")
                return

            playlist_name = playlist_info.get("name", "")
            logger.info(
                f"[AsyncPlaylist] 拉取到 {len(raw_tracks)} 首歌单歌曲: {playlist_name}"
            )

            # ── 构建网易云歌曲列表 ──
            netease_tracks = _build_recommend_tracks(
                raw_tracks, source_type,
                playlist_name or "网易云热榜",
                local_tracks=None,  # 不加本地，纯网易云
            )

            # ── 筛选未匹配本地的歌曲 ──
            unmatched = [t for t in netease_tracks if t.bpm < 0 and t.source == "netease"]
            logger.info(
                f"[AsyncPlaylist] 其中 {len(unmatched)} 首未在本地库，将下载+打分"
            )

            if unmatched:
                _async_download_and_score(unmatched, cookies, username)

        except Exception as e:
            logger.warning(f"[AsyncPlaylist] 后台歌单解析失败: {e}")

    t = threading.Thread(
        target=_worker, daemon=True, name="async-netease-playlist"
    )
    t.start()
    logger.info(f"[AsyncPlaylist] 已启动后台歌单解析线程 (playlist_id={playlist_id})")


# ══════════════════════════════════════════════════════════════════════
#  异步下载 + 自动打分（后台线程，不阻塞推荐响应）
# ══════════════════════════════════════════════════════════════════════


def _async_download_and_score(
    tracks: List[RecommendTrack],
    cookies: Dict[str, str],
    username: str = "admin",
) -> None:
    """
    后台线程：下载在线歌曲 → CAS 存储 → 自动打分 → 写入 DB。

    对 source="netease" 且 bpm < 0（未匹配本地特征库）的歌曲：
      1. url_v1() 获取下载链接
      2. SongStorageService.download_and_store() → CAS 存储
      3. _score_single_track() → librosa + PANNs + LLM + 评分 → 写入 DB
      4. user_track_behaviors 插入初始记录
    """
    import threading

    def _worker() -> None:
        try:
            from music_api import url_v1
            from music_downloader import MusicDownloader
            from services.song_storage import SongStorageService

            storage = SongStorageService()
            downloader = MusicDownloader()

            for track in tracks:
                try:
                    song_id = track.track_id
                    title = track.title
                    artist = track.artist
                    logger.info(f"[Async] 开始处理: {title} - {artist} (id={song_id})")

                    # Step 1: 获取下载链接
                    download_url = url_v1(song_id, "exhigh", cookies)
                    if not download_url:
                        logger.warning(f"[Async] 无法获取下载链接: {title}")
                        continue

                    # Step 2: CAS 下载存储
                    store_path, content_hash = storage.download_and_store(
                        username=username,
                        download_url=download_url,
                        metadata={
                            "title": title,
                            "artist": artist,
                            "ext": "mp3",
                        },
                    )
                    logger.info(f"[Async] CAS 存储完成: {store_path}")

                    # Step 3: 自动打分（librosa + PANNs + LLM + scoring → DB）
                    try:
                        from music_processor.single_scorer import score_single_track

                        score_result = score_single_track(
                            file_path=str(store_path),
                            title=title,
                            artist=artist,
                            album=track.album,
                            username=username,
                        )
                        logger.info(
                            f"[Async] 打分完成: {title}, "
                            f"pref_score={score_result.get('preference_score', 0)}"
                        )
                    except ImportError:
                        logger.warning("[Async] single_scorer 模块不可用，跳过打分")
                    except Exception as e:
                        logger.warning(f"[Async] 打分失败: {title}, error={e}")

                    # Step 4: 确保 user_track_behaviors 有记录
                    _ensure_user_behavior(str(store_path), username)

                except Exception as e:
                    logger.warning(f"[Async] 处理歌曲失败: {track.title}, error={e}")
                    continue

            logger.info(f"[Async] 后台下载打分完成，共处理 {len(tracks)} 首")

        except Exception as e:
            logger.error(f"[Async] 后台线程异常: {e}")

    t = threading.Thread(target=_worker, daemon=True, name="async-download-score")
    t.start()
    logger.info(f"[Async] 已启动后台下载打分线程 ({len(tracks)} 首)")


def _ensure_user_behavior(file_path: str, username: str = "admin") -> None:
    """确保 user_track_behaviors 中存在该歌曲记录（幂等）"""
    db_path = str(_PROJECT_ROOT / "config" / "music_vault.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO user_track_behaviors "
            "(track_id, username, is_favorite) "
            "SELECT id, ?, 0 FROM music_tracks WHERE file_path = ?",
            (username, file_path),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"写入 user_track_behaviors 失败: {e}")
