"""
Pydantic 请求/响应 Schema — 推荐系统 v3 数据模型

职责：定义 API 的输入输出数据结构，与业务逻辑完全解耦。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ──────────────────── 特征维度常量 ────────────────────
FEATURE_KEYS: List[str] = [
    "tempo", "energy", "vocal_ratio", "bass_intensity", "acousticness",
    "electronic_score", "rock_score", "instrument_pureness",
    "midnight_emo", "guofeng_vibe",
]


# ──────────────────── 请求模型 ────────────────────

class TrackFeature(BaseModel):
    """单首歌曲的 10 维特征"""
    track_id: str = Field(..., description="歌曲唯一 ID")
    title: str = Field(default="", description="歌曲名")
    artist: str = Field(default="", description="歌手名")
    features: Dict[str, float] = Field(
        ..., description=f"10 维特征字典，key: {', '.join(FEATURE_KEYS[:5])}..."
    )

    @field_validator("features")
    @classmethod
    def check_features(cls, v: Dict[str, float]) -> Dict[str, float]:
        missing = [fk for fk in FEATURE_KEYS if fk not in v]
        if missing:
            raise ValueError(f"缺少特征维度: {missing}")
        for fk, fv in v.items():
            if not (0 <= fv <= 100):
                raise ValueError(f"特征 '{fk}' 值 {fv} 超出 [0, 100]")
        return v


class RankRequest(BaseModel):
    """推荐排序请求"""
    tracks: List[TrackFeature] = Field(..., min_length=1, description="待排序歌曲列表")
    hour: Optional[int] = Field(default=None, ge=0, le=23, description="指定小时（默认当前）")
    slot: Optional[str] = Field(default=None, description="指定时段（优先级高于 hour）")


class TrackRadarInput(BaseModel):
    """前端雷达数组格式输入"""
    radar: List[float] = Field(..., min_length=10, max_length=10, description="10 维雷达数组 [0-100]")
    track_id: str = Field(default="")
    title: str = Field(default="")
    artist: str = Field(default="")


class RankRadarRequest(BaseModel):
    """雷达数组排序请求"""
    tracks: List[TrackRadarInput] = Field(..., min_length=1)
    hour: Optional[int] = Field(default=None, ge=0, le=23)
    slot: Optional[str] = Field(default=None)


# ──────────────────── 响应模型 ────────────────────

class RankedTrackOut(BaseModel):
    """排序后的单首歌曲"""
    track_id: str
    title: str
    artist: str
    final_score: float
    applied_slot: str
    slot_label: str
    raw_features: Dict[str, float]
    applied_weights: Dict[str, float]


class RankResponse(BaseModel):
    """排序响应"""
    ranked: List[RankedTrackOut]
    total: int
    applied_slot: Optional[str] = None
    slot_label: Optional[str] = None


class SlotInfo(BaseModel):
    """时段信息"""
    hour: int
    slot: str
    slot_label: str
    weights: Dict[str, float]
    all_slots: List[str]


class WeightSlotConfig(BaseModel):
    """单时段权重配置"""
    weights: Dict[str, float]


class WeightConfigOut(BaseModel):
    """权重配置响应"""
    version: str = "1.0.0"
    description: str = ""
    slots: Dict[str, WeightSlotConfig]


# ──────────────────── API 统一响应包装 ────────────────────

class APIResponse(BaseModel):
    """统一 API 响应格式"""
    status: int = 200
    success: bool = True
    message: str = "success"
    data: Any = None

    @classmethod
    def ok(cls, data: Any = None, message: str = "success") -> "APIResponse":
        return cls(status=200, success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str, status: int = 400) -> "APIResponse":
        return cls(status=status, success=False, message=message)
