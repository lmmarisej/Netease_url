"""
推荐路由 — 只做参数校验和服务调用，零业务逻辑
"""

from fastapi import APIRouter, HTTPException

from models.schemas import (
    APIResponse,
    RankRequest,
    RankRadarRequest,
)
from services.recommendation import RecommendationService

router = APIRouter(prefix="/api/v3/recommend", tags=["推荐"])


def _get_service() -> RecommendationService:
    """依赖注入：获取推荐服务单例"""
    from services.recommendation import RecommendationService
    return RecommendationService()


@router.post("/rank")
async def recommend_rank(req: RankRequest):
    """按当前时段权重排序歌曲列表"""
    try:
        svc = _get_service()
        result = svc.rank(
            [t.model_dump() for t in req.tracks],
            hour=req.hour,
            slot=req.slot,
        )
        return APIResponse.ok(result.model_dump(), "推荐排序完成")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rank-radar")
async def recommend_rank_radar(req: RankRadarRequest):
    """接收雷达数组格式排序"""
    try:
        svc = _get_service()
        result = svc.rank_from_radar(req.tracks, hour=req.hour, slot=req.slot)
        return APIResponse.ok(result.model_dump(), "雷达排序完成")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slot")
async def get_current_slot():
    """查询当前时段及权重"""
    try:
        svc = _get_service()
        info = svc.get_current_slot()
        return APIResponse.ok(info.model_dump(), "时段查询成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
