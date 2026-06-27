"""
FastAPI 主应用 — 音乐推荐排序 API v3（解耦版）

架构：Router → Service → Repository / Engine

启动方式:
    uvicorn backend.fastapi_app:app --host 0.0.0.0 --port 5001
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import (
    recommendation_router,
    config_router,
    playback_router,
    health_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("fastapi_v3")

app = FastAPI(
    title="音乐推荐排序 API v3",
    description="基于动态时间权重的歌曲推荐排序服务（Router-Service-Repository 架构）",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendation_router)
app.include_router(config_router)
app.include_router(playback_router)
app.include_router(health_router)

@app.on_event("startup")
async def startup():
    logger.info("FastAPI v3 (Router-Service-Repository) 已启动")

@app.get("/")
async def root():
    return {
        "service": "music-recommendation-v3",
        "version": "3.0.0",
        "architecture": "Router-Service-Repository",
        "endpoints": {
            "/api/v3/recommend/rank": "POST - 推荐排序",
            "/api/v3/recommend/rank-radar": "POST - 雷达排序",
            "/api/v3/recommend/slot": "GET - 时段查询",
            "/api/v3/config/weights": "GET/POST - 权重配置",
            "/api/v3/playback/log": "POST - 播放埋点",
            "/api/v3/health": "GET - 健康检查",
        },
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("启动 FastAPI v3 (Router-Service-Repository)")
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
