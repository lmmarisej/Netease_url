"""
FastAPI 独立应用 — 动态时间权重音乐推荐 API (v3)
===================================================
独立运行，不依赖 Flask。

启动方式:
    uvicorn backend.fastapi_app:app --host 0.0.0.0 --port 5001

或直接:
    python backend/fastapi_app.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# 路径设置
sys.path.insert(0, str(Path(__file__).resolve().parent))

from recommendation_engine import (
    AdvancedMusicRecommendationEngine,
    get_recommendation_engine,
    FEATURE_KEYS,
    SLOT_HOUR_RANGES,
)
from playback_api import router as playback_router

# ────────────────────────── 日志 ──────────────────────────
logger = logging.getLogger("fastapi_v3")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# ────────────────────────── 应用初始化 ──────────────────────────
app = FastAPI(
    title="音乐推荐排序 API v3",
    description="基于动态时间权重的歌曲推荐排序服务",
    version="3.0.0",
)

engine: AdvancedMusicRecommendationEngine = get_recommendation_engine()

# ── 注册子路由 ──
app.include_router(playback_router)


# ────────────────────────── Pydantic 模型 ──────────────────────────

class TrackFeature(BaseModel):
    track_id: str = Field(..., description="歌曲唯一ID")
    title: str = Field(default="", description="歌曲名")
    artist: str = Field(default="", description="歌手名")
    features: Dict[str, float] = Field(
        ..., description="10维特征字典，key: tempo/energy/vocal_ratio/..."
    )

    @field_validator("features")
    @classmethod
    def check_features(cls, v: Dict[str, float]) -> Dict[str, float]:
        missing = [fk for fk in FEATURE_KEYS if fk not in v]
        if missing:
            raise ValueError(f"缺少特征维度: {missing}")
        for fk, fv in v.items():
            if not (0 <= fv <= 100):
                raise ValueError(f"特征 '{fk}' 值 {fv} 超出 [0, 100] 范围")
        return v


class RankRequest(BaseModel):
    tracks: List[TrackFeature] = Field(..., min_length=1, description="待排序歌曲列表")
    hour: Optional[int] = Field(default=None, ge=0, le=23, description="指定小时（默认服务器当前小时）")
    slot: Optional[str] = Field(default=None, description="指定时段（优先级高于hour）")


class WeightSlot(BaseModel):
    weights: Dict[str, float] = Field(..., description="10维权重")


class WeightConfig(BaseModel):
    version: str = Field(default="1.0.0")
    description: str = Field(default="")
    slots: Dict[str, WeightSlot]


class TrackInput(BaseModel):
    """兼容前端直接传雷达数组 + meta 的格式"""
    radar: List[float] = Field(..., min_length=10, max_length=10, description="10维雷达数组 [0-100]")
    track_id: str = ""
    title: str = ""
    artist: str = ""


class RankRadarRequest(BaseModel):
    tracks: List[TrackInput] = Field(..., min_length=1)
    hour: Optional[int] = Field(default=None, ge=0, le=23)
    slot: Optional[str] = Field(default=None)


# ────────────────────────── 路由 ──────────────────────────

@app.get("/api/v3/config/weights", tags=["配置"])
async def get_weights() -> JSONResponse:
    """读取完整权重配置"""
    try:
        config = engine.get_config()
        return JSONResponse(content={"status": 200, "success": True, "data": config})
    except Exception as e:
        logger.error(f"读取权重配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v3/config/weights", tags=["配置"])
async def save_weights(payload: Dict[str, Any]) -> JSONResponse:
    """覆盖写入权重配置"""
    try:
        ok, msg = engine.save_config(payload)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return JSONResponse(content={"status": 200, "success": True, "message": msg})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存权重配置异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v3/recommend/rank", tags=["推荐"])
async def recommend_rank(req: RankRequest) -> JSONResponse:
    """接收歌曲列表，按当前时段权重排序"""
    try:
        tracks_data = [t.model_dump() for t in req.tracks]
        ranked = engine.rank_tracks_to_dict(
            tracks_data,
            hour=req.hour,
            slot=req.slot,
        )
        return JSONResponse(content={
            "status": 200, "success": True,
            "data": {
                "ranked": ranked,
                "total": len(ranked),
                "applied_slot": ranked[0]["applied_slot"] if ranked else None,
                "slot_label": ranked[0]["slot_label"] if ranked else None,
            },
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"推荐排序异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v3/recommend/rank-radar", tags=["推荐"])
async def recommend_rank_radar(req: RankRadarRequest) -> JSONResponse:
    """
    接收雷达数组格式的歌曲列表，自动转为引擎消费格式后排序。
    适用于前端直接传入 10 维雷达数组的场景。
    """
    try:
        tracks_data = [
            engine.build_track_from_radar(t.radar, {
                "track_id": t.track_id,
                "title": t.title,
                "artist": t.artist,
            })
            for t in req.tracks
        ]
        ranked = engine.rank_tracks_to_dict(
            tracks_data,
            hour=req.hour,
            slot=req.slot,
        )
        return JSONResponse(content={
            "status": 200, "success": True,
            "data": {
                "ranked": ranked,
                "total": len(ranked),
                "applied_slot": ranked[0]["applied_slot"] if ranked else None,
                "slot_label": ranked[0]["slot_label"] if ranked else None,
            },
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"雷达排序异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/recommend/slot", tags=["推荐"])
async def get_current_slot() -> JSONResponse:
    """查询当前时段及权重"""
    try:
        info = engine.get_current_slot_info()
        return JSONResponse(content={"status": 200, "success": True, "data": info})
    except Exception as e:
        logger.error(f"查询时段异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/health", tags=["系统"])
async def health() -> JSONResponse:
    """健康检查"""
    return JSONResponse(content={
        "status": 200, "success": True,
        "data": {"service": "recommendation-v3", "timestamp": int(time.time())},
    })


# ────────────────────────── 启动入口 ──────────────────────────
if __name__ == "__main__":
    import uvicorn

    logger.info("启动 FastAPI 推荐服务 v3 (端口 5001)")
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
