"""健康检查路由"""

import time

from fastapi import APIRouter

from models.schemas import APIResponse

router = APIRouter(prefix="/api/v3", tags=["系统"])


@router.get("/health")
async def health():
    return APIResponse.ok({
        "service": "recommendation-v3",
        "timestamp": int(time.time()),
    }, "服务正常")
