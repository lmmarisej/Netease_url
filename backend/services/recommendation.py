"""
RecommendationService — 推荐排序业务逻辑

职责：
- 根据当前/指定时间选择权重模板
- 调用 Engine 执行加权排序
- 纯业务逻辑，不接触 HTTP/DB
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from models.schemas import (
    FEATURE_KEYS,
    RankedTrackOut,
    RankResponse,
    SlotInfo,
    TrackRadarInput,
)
from repositories.weight_repo import WeightConfigRepository
from recommendation_engine import (
    AdvancedMusicRecommendationEngine,
    SLOT_HOUR_RANGES,
)

logger = logging.getLogger("recommendation_service")


class RecommendationService:
    """推荐排序业务服务"""

    def __init__(
        self,
        weight_repo: WeightConfigRepository | None = None,
        engine: AdvancedMusicRecommendationEngine | None = None,
    ):
        self._weight_repo = weight_repo or WeightConfigRepository()
        self._engine = engine or AdvancedMusicRecommendationEngine(
            config_dir=self._weight_repo._config_dir
        )
        # 确保引擎配置与仓库同步
        self._engine.load_config()

    # ── 排序入口 ──

    def rank(
        self,
        tracks: List[Dict],
        hour: int | None = None,
        slot: str | None = None,
    ) -> RankResponse:
        """
        对歌曲列表按时段权重排序。

        Args:
            tracks: 歌曲列表，每项含 features 字典 (10 维) + track_id/title/artist
            hour: 指定小时，默认当前
            slot: 指定时段，优先于 hour

        Returns:
            RankResponse (含 ranked 列表、时段信息)
        """
        if not tracks:
            return RankResponse(ranked=[], total=0)

        # 确定时段
        if slot and slot not in SLOT_HOUR_RANGES:
            raise ValueError(f"无效时段: '{slot}'")

        applied = slot or self._engine.get_current_time_slot(
            hour if hour is not None else time.localtime().tm_hour
        )
        config = self._weight_repo.read()
        slot_data = config.get("slots", {}).get(applied, {})
        weights = slot_data.get("weights", {})
        label = slot_data.get("label", applied)

        # 执行排序
        raw_results = self._engine.rank_tracks(tracks, hour=hour, slot=slot)
        ranked = [
            RankedTrackOut(
                track_id=r.track_id,
                title=r.title,
                artist=r.artist,
                final_score=r.final_score,
                applied_slot=r.applied_slot,
                slot_label=r.slot_label,
                raw_features=r.raw_features,
                applied_weights=r.applied_weights,
            )
            for r in raw_results
        ]

        logger.info(
            f"推荐排序完成: slot={applied}({label}), "
            f"input={len(tracks)}, ranked={len(ranked)}"
        )
        return RankResponse(
            ranked=ranked,
            total=len(ranked),
            applied_slot=applied,
            slot_label=label,
        )

    def rank_from_radar(
        self,
        radar_tracks: List[TrackRadarInput],
        hour: int | None = None,
        slot: str | None = None,
    ) -> RankResponse:
        """
        接收雷达数组格式，自动转为引擎消费格式后排序。
        """
        converted = [
            self._engine.build_track_from_radar(t.radar, {
                "track_id": t.track_id,
                "title": t.title,
                "artist": t.artist,
            })
            for t in radar_tracks
        ]
        return self.rank(converted, hour=hour, slot=slot)

    # ── 时段查询 ──

    def get_current_slot(self) -> SlotInfo:
        """获取当前时段信息"""
        now = time.localtime()
        config = self._weight_repo.read()
        slot = self._engine.get_current_time_slot(now.tm_hour)
        slot_data = config.get("slots", {}).get(slot, {})
        return SlotInfo(
            hour=now.tm_hour,
            slot=slot,
            slot_label=slot_data.get("label", slot),
            weights=slot_data.get("weights", {}),
            all_slots=list(config.get("slots", {}).keys()),
        )

    # ── 配置管理 ──

    def get_weights_config(self) -> Dict:
        """读取完整权重配置"""
        return self._weight_repo.read()

    def save_weights_config(self, new_config: Dict) -> tuple[bool, str]:
        """保存权重配置（含校验）"""
        ok, msg = self._weight_repo.write(new_config)
        if ok:
            # 同步引擎
            self._engine.load_config()
        return ok, msg
