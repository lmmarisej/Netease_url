"""
播放行为埋点路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.schemas import APIResponse
from services.playback_log import PlaybackLogService

router = APIRouter(prefix="/api/v3/playback", tags=["播放行为"])


class PlaybackLogRequest(BaseModel):
    track_id: int = Field(..., description="歌曲 ID")
    username: str = Field(default="admin", description="用户名")
    play_duration_sec: float = Field(..., ge=0, description="播放时长（秒）")
    total_duration_sec: float = Field(default=0.0, ge=0, description="歌曲总时长")
    skip_threshold_sec: float = Field(default=5.0, ge=0, description="跳过阈值")


def _get_service() -> PlaybackLogService:
    return PlaybackLogService()


@router.post("/log")
async def log_playback(req: PlaybackLogRequest):
    """记录一次播放行为"""
    try:
        svc = _get_service()
        svc.log_playback(
            track_id=req.track_id,
            username=req.username,
            play_duration_sec=req.play_duration_sec,
            total_duration_sec=req.total_duration_sec,
            skip_threshold_sec=req.skip_threshold_sec,
        )
        return APIResponse.ok(None, "播放记录已保存")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/behavior/{username}/{track_id}")
async def get_behavior(username: str, track_id: int):
    """查询单曲用户行为"""
    try:
        svc = _get_service()
        behavior = svc.get_behavior(track_id, username)
        if not behavior:
            raise HTTPException(status_code=404, detail="无行为记录")
        return APIResponse.ok({
            "track_id": behavior.track_id,
            "username": behavior.username,
            "is_favorite": behavior.is_favorite,
            "completion_rate": behavior.completion_rate,
            "skip_count": behavior.skip_count,
            "last_played_at": behavior.last_played_at,
        }, "行为查询成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
