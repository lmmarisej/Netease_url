"""
Advanced Music Recommendation Engine (高级音乐推荐引擎)
=====================================================
基于动态时间权重的歌曲推荐排序模块。

核心功能：
- 时段感知：根据服务器当前小时自动切换权重模板
- 10维特征加权排序：Σ(Feature_Raw_Value_i × Weight_i)
- 原子写入配置：先写 .tmp 再 rename，防止崩溃损坏
- 线程安全：threading.Lock 保护配置读写

特征维度（0-100 分）：
  声学/声源 (Librosa/Demucs): tempo, energy, vocal_ratio, bass_intensity, acousticness
  流派/乐器 (PANNs):           electronic_score, rock_score, instrument_pureness
  歌词意境 (Ollama LLM):        midnight_emo, guofeng_vibe
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("recommendation_engine")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ────────────────────────── 默认时段配置 ──────────────────────────
_DEFAULT_WEIGHT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "slots": {
        "morning": {
            "label": "清晨 (07:00-09:00)",
            "weights": {"tempo": 1.2, "energy": 0.8, "vocal_ratio": 0.9, "bass_intensity": 0.7,
                        "acousticness": 1.3, "electronic_score": 0.5, "rock_score": 0.4,
                        "instrument_pureness": 1.2, "midnight_emo": 0.3, "guofeng_vibe": 1.1},
        },
        "daytime": {
            "label": "白天 (09:00-18:00)",
            "weights": {"tempo": 1.1, "energy": 1.0, "vocal_ratio": 1.3, "bass_intensity": 1.0,
                        "acousticness": 0.8, "electronic_score": 1.0, "rock_score": 0.9,
                        "instrument_pureness": 1.5, "midnight_emo": 0.5, "guofeng_vibe": 1.0},
        },
        "evening": {
            "label": "傍晚 (18:00-22:00)",
            "weights": {"tempo": 1.0, "energy": 1.3, "vocal_ratio": 1.2, "bass_intensity": 1.4,
                        "acousticness": 0.6, "electronic_score": 1.3, "rock_score": 1.1,
                        "instrument_pureness": 0.8, "midnight_emo": 1.0, "guofeng_vibe": 0.9},
        },
        "midnight": {
            "label": "深夜 (22:00-07:00)",
            "weights": {"tempo": 0.5, "energy": 0.2, "vocal_ratio": 1.4, "bass_intensity": 0.8,
                        "acousticness": 1.2, "electronic_score": 0.7, "rock_score": 0.3,
                        "instrument_pureness": 1.1, "midnight_emo": 1.7, "guofeng_vibe": 1.0},
        },
    },
}

# 10 维特征 key 列表
FEATURE_KEYS: List[str] = [
    "tempo", "energy", "vocal_ratio", "bass_intensity", "acousticness",
    "electronic_score", "rock_score", "instrument_pureness",
    "midnight_emo", "guofeng_vibe",
]

# 时段 → 小时范围映射
SLOT_HOUR_RANGES: Dict[str, Tuple[int, int]] = {
    "morning":  (7, 9),    # [7, 9)
    "daytime":  (9, 18),   # [9, 18)
    "evening":  (18, 22),  # [18, 22)
    "midnight": (22, 7),   # [22, 24) U [0, 7)
}


@dataclass
class RankedTrack:
    """排序后的歌曲结果"""
    track_id: str
    title: str = ""
    artist: str = ""
    final_score: float = 0.0
    applied_slot: str = ""
    slot_label: str = ""
    raw_features: Dict[str, float] = field(default_factory=dict)
    applied_weights: Dict[str, float] = field(default_factory=dict)


class AdvancedMusicRecommendationEngine:
    """高级音乐推荐引擎 — 基于动态时间权重的歌曲排序"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Args:
            config_dir: 配置文件目录，默认为项目根目录下的 config/
        """
        if config_dir is None:
            # 自动推导项目根目录：本文件在 backend/ 下
            config_dir = Path(__file__).resolve().parent.parent / "config"
        self._config_dir = config_dir
        self._config_path = config_dir / "weight_config.json"
        self._lock = threading.Lock()
        self._config: Dict[str, Any] = {}
        logger.info(f"RecommendationEngine 初始化，配置文件路径: {self._config_path}")

    # ──────────────────── 配置管理 ────────────────────

    def load_config(self) -> Dict[str, Any]:
        """加载权重配置，不存在时自动初始化默认配置"""
        with self._lock:
            try:
                if self._config_path.exists():
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        self._config = json.load(f)
                    logger.info(f"已加载权重配置: {self._config_path}")
                else:
                    logger.info("权重配置文件不存在，初始化默认配置")
                    self._save_atomic(_DEFAULT_WEIGHT_CONFIG)
                    self._config = json.loads(json.dumps(_DEFAULT_WEIGHT_CONFIG))
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"加载权重配置失败，回退到默认配置: {e}")
                self._config = json.loads(json.dumps(_DEFAULT_WEIGHT_CONFIG))
        return self._config

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置（只读副本）"""
        with self._lock:
            if not self._config:
                self.load_config()
            return json.loads(json.dumps(self._config))

    def save_config(self, new_config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        覆盖写入配置，含格式校验。

        Returns:
            (success, message)
        """
        with self._lock:
            try:
                # ── 格式校验 ──
                if "slots" not in new_config:
                    return False, "缺少 'slots' 字段"
                slots = new_config["slots"]
                if not isinstance(slots, dict):
                    return False, "'slots' 必须是字典"

                valid_slot_keys = set(SLOT_HOUR_RANGES.keys())
                for slot_key, slot_data in slots.items():
                    if slot_key not in valid_slot_keys:
                        return False, f"无效时段key: '{slot_key}'，有效值: {sorted(valid_slot_keys)}"
                    if "weights" not in slot_data:
                        return False, f"时段 '{slot_key}' 缺少 'weights'"
                    weights = slot_data["weights"]
                    if not isinstance(weights, dict):
                        return False, f"时段 '{slot_key}' 的 'weights' 必须是字典"

                    for fk in FEATURE_KEYS:
                        if fk not in weights:
                            return False, f"时段 '{slot_key}' 缺少特征权重: '{fk}'"
                        w = weights[fk]
                        if not isinstance(w, (int, float)):
                            return False, f"时段 '{slot_key}.{fk}' 权重必须是数字"

                # ── 版本号自动递增 ──
                new_config.setdefault("version", "1.0.0")
                new_config.setdefault("description", self._config.get("description", ""))

                self._save_atomic(new_config)
                self._config = new_config
                logger.info("权重配置已更新并持久化")
                return True, "配置保存成功"
            except Exception as e:
                logger.error(f"保存配置异常: {e}")
                return False, f"保存失败: {str(e)}"

    def _save_atomic(self, data: Dict[str, Any]) -> None:
        """原子写入：先写 .tmp 再 rename，防止崩溃损坏"""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self._config_path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._config_path)  # 原子 rename
            logger.debug(f"配置原子写入成功: {self._config_path}")
        except Exception:
            # 清理临时文件
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    # ──────────────────── 时段映射 ────────────────────

    @staticmethod
    def get_current_time_slot(hour: int) -> str:
        """
        24小时制 → 时段 key。

        规则：
            07 ≤ hour < 09  → morning
            09 ≤ hour < 18  → daytime
            18 ≤ hour < 22  → evening
            22 ≤ hour < 24  → midnight
             0 ≤ hour < 7   → midnight

        Raises:
            ValueError: hour 不在 [0, 23]
        """
        if not 0 <= hour <= 23:
            raise ValueError(f"hour 必须在 [0, 23]，收到: {hour}")
        if 7 <= hour < 9:
            return "morning"
        if 9 <= hour < 18:
            return "daytime"
        if 18 <= hour < 22:
            return "evening"
        return "midnight"  # 22-23 或 0-6

    def get_current_slot_info(self) -> Dict[str, Any]:
        """获取当前时段及对应权重"""
        config = self.get_config()
        hour = time.localtime().tm_hour
        slot = self.get_current_time_slot(hour)
        slot_data = config.get("slots", {}).get(slot, {})
        return {
            "hour": hour,
            "slot": slot,
            "slot_label": slot_data.get("label", slot),
            "weights": slot_data.get("weights", _DEFAULT_WEIGHT_CONFIG["slots"][slot]["weights"]),
            "all_slots": list(config.get("slots", {}).keys()),
        }

    # ──────────────────── 排序核心 ────────────────────

    @staticmethod
    def build_track_from_radar(radar: List[float], track_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 10 维雷达数组 (0-100) 转为引擎消费格式。

        Args:
            radar:  10 个浮点数，顺序对应 FEATURE_KEYS
            track_meta: { "track_id", "title", "artist", ... }

        Returns:
            含 features 字典的 track 数据
        """
        if len(radar) != len(FEATURE_KEYS):
            raise ValueError(f"雷达数组长度必须为 {len(FEATURE_KEYS)}，收到: {len(radar)}")
        features = {FEATURE_KEYS[i]: float(radar[i]) for i in range(len(FEATURE_KEYS))}
        return {
            "track_id": str(track_meta.get("track_id", track_meta.get("id", ""))),
            "title": track_meta.get("title", track_meta.get("name", "")),
            "artist": track_meta.get("artist", ""),
            "features": features,
            **{k: v for k, v in track_meta.items() if k not in ("track_id", "title", "artist", "id", "name")},
        }

    def rank_tracks(
        self,
        tracks_list: List[Dict[str, Any]],
        hour: Optional[int] = None,
        slot: Optional[str] = None,
    ) -> List[RankedTrack]:
        """
        按当前时段权重对歌曲列表排序。

        Args:
            tracks_list: 歌曲列表，每项需含 "features" 字典 (10维) + "track_id"
            hour:       指定小时 (默认服务器当前小时)
            slot:       指定时段 (优先级高于 hour)

        Returns:
            按 final_score 降序排列的 RankedTrack 列表
        """
        if not tracks_list:
            return []

        # 确定时段
        if slot:
            if slot not in SLOT_HOUR_RANGES:
                raise ValueError(f"无效时段: '{slot}'，有效值: {sorted(SLOT_HOUR_RANGES.keys())}")
            applied_slot = slot
        else:
            h = hour if hour is not None else time.localtime().tm_hour
            applied_slot = self.get_current_time_slot(h)

        config = self.get_config()
        slot_data = config.get("slots", {}).get(applied_slot, {})
        weights = slot_data.get("weights", _DEFAULT_WEIGHT_CONFIG["slots"][applied_slot]["weights"])
        slot_label = slot_data.get("label", applied_slot)

        ranked: List[RankedTrack] = []
        for track in tracks_list:
            features = track.get("features", {})
            if len(features) < len(FEATURE_KEYS):
                logger.warning(f"歌曲 {track.get('track_id', '?')} 特征不完整，跳过")
                continue

            # 加权求和
            final_score = 0.0
            for fk in FEATURE_KEYS:
                final_score += features.get(fk, 0.0) * weights.get(fk, 1.0)

            ranked.append(RankedTrack(
                track_id=str(track.get("track_id", "")),
                title=track.get("title", track.get("name", "")),
                artist=track.get("artist", ""),
                final_score=round(final_score, 2),
                applied_slot=applied_slot,
                slot_label=slot_label,
                raw_features={fk: features.get(fk, 0.0) for fk in FEATURE_KEYS},
                applied_weights=dict(weights),
            ))

        # 降序排列
        ranked.sort(key=lambda x: x.final_score, reverse=True)

        logger.info(
            f"推荐排序完成: 时段={applied_slot}({slot_label}), "
            f"输入={len(tracks_list)}首, 有效={len(ranked)}首, "
            f"Top1={ranked[0].title if ranked else 'N/A'}"
        )
        return ranked

    def rank_tracks_to_dict(self, tracks_list: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """排序并转为 dict 列表（便于 JSON 序列化）"""
        ranked = self.rank_tracks(tracks_list, **kwargs)
        return [
            {
                "track_id": r.track_id,
                "title": r.title,
                "artist": r.artist,
                "final_score": r.final_score,
                "applied_slot": r.applied_slot,
                "slot_label": r.slot_label,
                "raw_features": r.raw_features,
                "applied_weights": r.applied_weights,
            }
            for r in ranked
        ]


# ──────────────────── 全局单例 ────────────────────
_engine_instance: Optional[AdvancedMusicRecommendationEngine] = None
_engine_lock = threading.Lock()


def get_recommendation_engine(config_dir: Optional[Path] = None) -> AdvancedMusicRecommendationEngine:
    """获取推荐引擎全局单例（线程安全）"""
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = AdvancedMusicRecommendationEngine(config_dir)
                _engine_instance.load_config()
    return _engine_instance
