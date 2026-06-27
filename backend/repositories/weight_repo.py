"""
WeightConfigRepository — 权重配置持久化（JSON 文件 + 原子写入）

职责：仅负责配置的读写和格式校验，不包含业务逻辑。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Tuple

logger = logging.getLogger("weight_repo")

# 10 维特征 key
FEATURE_KEYS = [
    "tempo", "energy", "vocal_ratio", "bass_intensity", "acousticness",
    "electronic_score", "rock_score", "instrument_pureness",
    "midnight_emo", "guofeng_vibe",
]

_DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "slots": {
        "morning":  {"label": "清晨 (07:00-09:00)", "weights": {"tempo": 1.2, "energy": 0.8, "vocal_ratio": 0.9, "bass_intensity": 0.7, "acousticness": 1.3, "electronic_score": 0.5, "rock_score": 0.4, "instrument_pureness": 1.2, "midnight_emo": 0.3, "guofeng_vibe": 1.1}},
        "daytime":  {"label": "白天 (09:00-18:00)", "weights": {"tempo": 1.1, "energy": 1.0, "vocal_ratio": 1.3, "bass_intensity": 1.0, "acousticness": 0.8, "electronic_score": 1.0, "rock_score": 0.9, "instrument_pureness": 1.5, "midnight_emo": 0.5, "guofeng_vibe": 1.0}},
        "evening":  {"label": "傍晚 (18:00-22:00)", "weights": {"tempo": 1.0, "energy": 1.3, "vocal_ratio": 1.2, "bass_intensity": 1.4, "acousticness": 0.6, "electronic_score": 1.3, "rock_score": 1.1, "instrument_pureness": 0.8, "midnight_emo": 1.0, "guofeng_vibe": 0.9}},
        "midnight": {"label": "深夜 (22:00-07:00)", "weights": {"tempo": 0.5, "energy": 0.2, "vocal_ratio": 1.4, "bass_intensity": 0.8, "acousticness": 1.2, "electronic_score": 0.7, "rock_score": 0.3, "instrument_pureness": 1.1, "midnight_emo": 1.7, "guofeng_vibe": 1.0}},
    },
}


class WeightConfigRepository:
    """权重配置 JSON 文件持久化仓库"""

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            config_dir = Path(__file__).resolve().parent.parent.parent / "config"
        self._config_dir = config_dir
        self._config_path = config_dir / "weight_config.json"
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] | None = None

    # ── 读 ──

    def read(self) -> Dict[str, Any]:
        """读取配置，首次自动初始化"""
        with self._lock:
            if self._cache is not None:
                return json.loads(json.dumps(self._cache))
            try:
                if self._config_path.exists():
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        self._cache = json.load(f)
                else:
                    self._cache = json.loads(json.dumps(_DEFAULT_CONFIG))
                    self._write_atomic(self._cache)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"读取配置失败，使用默认值: {e}")
                self._cache = json.loads(json.dumps(_DEFAULT_CONFIG))
            return json.loads(json.dumps(self._cache))

    # ── 写（校验 + 原子） ──

    def write(self, new_config: Dict[str, Any]) -> Tuple[bool, str]:
        """校验并持久化配置"""
        with self._lock:
            ok, msg = self._validate(new_config)
            if not ok:
                return False, msg
            new_config.setdefault("version", "1.0.0")
            new_config.setdefault("description", "")
            self._write_atomic(new_config)
            self._cache = new_config
            return True, "配置保存成功"

    def invalidate_cache(self) -> None:
        """清空缓存，下次读取时重新加载"""
        with self._lock:
            self._cache = None

    # ── 内部 ──

    def _validate(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        if "slots" not in config:
            return False, "缺少 'slots' 字段"
        slots = config["slots"]
        if not isinstance(slots, dict):
            return False, "'slots' 必须是字典"
        valid_keys = {"morning", "daytime", "evening", "midnight"}
        for sk, sv in slots.items():
            if sk not in valid_keys:
                return False, f"无效时段: '{sk}'，有效值: {sorted(valid_keys)}"
            weights = sv.get("weights", {})
            if not isinstance(weights, dict):
                return False, f"'{sk}' 的 weights 必须是字典"
            for fk in FEATURE_KEYS:
                if fk not in weights:
                    return False, f"'{sk}' 缺少特征: '{fk}'"
                if not isinstance(weights[fk], (int, float)):
                    return False, f"'{sk}.{fk}' 权重不是数字"
        return True, ""

    def _write_atomic(self, data: Dict[str, Any]) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._config_path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._config_path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
