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
    """推荐歌曲（含完整特征向量）"""

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


class RecommendResponse(BaseModel):
    """推荐接口响应"""

    total: int
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
        description="推荐来源: hot_list（网易云热榜）| custom_playlist（自定义歌单）",
    ),
    playlist_id: Optional[str] = Query(
        default=None,
        description="自定义歌单 ID（source_type=custom_playlist 时必填）",
    ),
) -> RecommendResponse:
    """
    核心推荐接口。

    - hot_list：拉取网易云热歌榜（ID=3778678），匹配本地特征库后返回
    - custom_playlist：拉取指定歌单，匹配本地特征库后返回

    特征匹配策略：
    1. 调用网易云 API 获取歌单内歌曲列表
    2. 按 title + artist 在本地 music_tracks 表中模糊匹配
    3. 匹配成功 → 从 track_audio_features + track_tags 读取真实特征
    4. 未匹配   → 返回基础元信息，特征置 -1 表示待扫描
    """
    # ── 参数校验 ──
    if source_type not in ("hot_list", "custom_playlist"):
        raise HTTPException(
            status_code=400,
            detail="source_type 仅支持 'hot_list' 或 'custom_playlist'",
        )

    if source_type == "custom_playlist" and not playlist_id:
        raise HTTPException(
            status_code=400,
            detail="source_type=custom_playlist 时必须提供 playlist_id",
        )

    # ── 获取 Cookie ──
    cookies = _load_netease_cookies()
    if not cookies:
        # 无有效 Cookie，回退为空列表（提示用户配置 Cookie）
        logger.warning("无有效网易云 Cookie，推荐接口返回空列表")
        return RecommendResponse(
            total=0,
            source_type=source_type,
            source_label="需要配置网易云 Cookie",
            generated_at=datetime.now(timezone.utc).isoformat(),
            tracks=[],
        )

    # ── 调用网易云 API ──
    pid = int(playlist_id) if playlist_id else _HOT_CHART_ID
    try:
        from music_api import playlist_detail, APIException as NeteaseAPIError

        playlist_info = playlist_detail(pid, cookies)
        raw_tracks = playlist_info.get("tracks", [])
    except NeteaseAPIError as e:
        logger.error(f"网易云 API 调用失败: {e}")
        raise HTTPException(status_code=502, detail=f"网易云 API 失败: {e}")
    except ImportError:
        logger.error("无法导入 music_api 模块")
        raise HTTPException(status_code=500, detail="后端 music_api 模块不可用")
    except Exception as e:
        logger.error(f"获取歌单异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if not raw_tracks:
        return RecommendResponse(
            total=0,
            source_type=source_type,
            source_label=playlist_info.get("name", "未知歌单"),
            generated_at=datetime.now(timezone.utc).isoformat(),
            tracks=[],
        )

    # ── 匹配本地特征库 ──
    tracks = _build_recommend_tracks(raw_tracks, source_type, playlist_info.get("name", ""))

    return RecommendResponse(
        total=len(tracks),
        source_type=source_type,
        source_label=playlist_info.get("name", "网易云热榜" if source_type == "hot_list" else ""),
        generated_at=datetime.now(timezone.utc).isoformat(),
        tracks=tracks,
    )


# ══════════════════════════════════════════════════════════════════════
#  真实数据获取 — 网易云 API + 本地特征库匹配
# ══════════════════════════════════════════════════════════════════════

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
) -> List[RecommendTrack]:
    """
    将网易云 API 返回的原始歌曲列表转换为 RecommendTrack 列表，
    每组数据优先匹配本地特征库。

    参数：
        raw_tracks: 网易云 API 返回的 tracks 数组
        source_type: "hot_list" | "custom_playlist"
        playlist_name: 歌单名称（用于 source_label）
    """
    result: List[RecommendTrack] = []
    source_label = playlist_name or ("网易云热榜" if source_type == "hot_list" else "")
    count_matched = 0

    for t in raw_tracks:
        track_id = str(t.get("id", ""))
        title = t.get("name", "")
        # 兼容两种格式：playlist_detail 简化格式 vs 原始 API 格式
        if "ar" in t:
            artist = ", ".join(ar.get("name", "") for ar in t.get("ar", []))
            album = t.get("al", {}).get("name", "")
            cover_url = t.get("al", {}).get("picUrl", "")
        else:
            artist = t.get("artists", "")
            album = t.get("album", "")
            cover_url = t.get("picUrl", "")

        # ── 查询本地特征 ──
        local = _get_local_features(title, artist)

        if local:
            count_matched += 1
            result.append(
                RecommendTrack(
                    track_id=track_id,
                    title=title,
                    artist=artist,
                    album=album,
                    cover_url=cover_url,
                    bpm=local["tempo"],
                    vocal_ratio=local["vocal_ratio"],
                    energy=local["energy"],
                    danceability=50.0,
                    acousticness=local["acousticness"],
                    instrumentalness=local["instrument_pureness"],
                    valence=local["midnight_emo"],
                    source_label=source_label,
                )
            )
        else:
            # 未匹配：保留元信息，特征置 -1 表示待扫描
            result.append(
                RecommendTrack(
                    track_id=track_id,
                    title=title,
                    artist=artist,
                    album=album,
                    cover_url=cover_url,
                    bpm=-1.0,
                    vocal_ratio=-1.0,
                    energy=-1.0,
                    danceability=-1.0,
                    acousticness=-1.0,
                    instrumentalness=-1.0,
                    valence=-1.0,
                    source_label=source_label,
                )
            )

    matched_ratio = count_matched * 100 / len(result) if result else 0
    logger.info(
        f"推荐构建完成: total={len(result)}, "
        f"matched={count_matched} ({matched_ratio:.0f}%), "
        f"source={source_label}"
    )
    return result
