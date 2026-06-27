"""
配置路由 — 权重配置读写
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from models.schemas import APIResponse
from services.recommendation import RecommendationService

router = APIRouter(prefix="/api/v3/config", tags=["配置"])


def _get_service() -> RecommendationService:
    from services.recommendation import RecommendationService
    return RecommendationService()


@router.get("/weights")
async def get_weights():
    """读取完整权重配置"""
    try:
        svc = _get_service()
        config = svc.get_weights_config()
        return APIResponse.ok(config, "权重配置获取成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weights")
async def save_weights(payload: Dict[str, Any]):
    """覆盖写入权重配置"""
    try:
        svc = _get_service()
        ok, msg = svc.save_weights_config(payload)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return APIResponse.ok(None, msg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
