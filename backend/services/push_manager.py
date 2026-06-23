"""
PushManagerService — 消息推送业务逻辑

从 push_manager.py 中提取纯业务编排逻辑，
与 Flask 路由注册解耦。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("push_manager_service")


class PushConfig:
    """推送配置数据类"""
    def __init__(self, data: Dict[str, Any] | None = None):
        d = data or {}
        self.pushplus_token: str = d.get("pushplus_token", "")
        self.serverchan_key: str = d.get("serverchan_key", "")
        self.wxpusher_token: str = d.get("wxpusher_token", "")
        self.wxpusher_topic_ids: List[str] = d.get("wxpusher_topic_ids", [])
        self.enable_push: bool = d.get("enable_push", False)
        self.enable_daily_report: bool = d.get("enable_daily_report", False)
        self.report_time: str = d.get("report_time", "09:00")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pushplus_token": self.pushplus_token,
            "serverchan_key": self.serverchan_key,
            "wxpusher_token": self.wxpusher_token,
            "wxpusher_topic_ids": self.wxpusher_topic_ids,
            "enable_push": self.enable_push,
            "enable_daily_report": self.enable_daily_report,
            "report_time": self.report_time,
        }


class PushManagerService:
    """推送管理服务"""

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            config_dir = Path(__file__).resolve().parent.parent / "config"
        self._config_dir = config_dir

    # ── 配置读写 ──

    def load_config(self, username: str = "admin") -> PushConfig:
        """加载用户推送配置"""
        path = self._config_dir / "users" / username / "push_config.json"
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return PushConfig(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"读取推送配置失败: {e}")
        return PushConfig()

    def save_config(self, username: str, config: PushConfig) -> bool:
        """保存用户推送配置"""
        path = self._config_dir / "users" / username / "push_config.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            logger.error(f"保存推送配置失败: {e}")
            return False

    # ── 推送发送 ──

    def send_push(self, username: str, title: str, content: str) -> Dict[str, Any]:
        """向用户发送推送通知"""
        config = self.load_config(username)
        if not config.enable_push:
            return {"success": False, "message": "推送未启用"}

        results = {}
        try:
            import requests
            # PushPlus
            if config.pushplus_token:
                r = requests.post("https://www.pushplus.plus/send", json={
                    "token": config.pushplus_token,
                    "title": title,
                    "content": content,
                }, timeout=10)
                results["pushplus"] = r.json() if r.ok else {"error": r.status_code}

            # ServerChan
            if config.serverchan_key:
                r = requests.post(f"https://sctapi.ftqq.com/{config.serverchan_key}.send", data={
                    "title": title, "desp": content,
                }, timeout=10)
                results["serverchan"] = r.json() if r.ok else {"error": r.status_code}

            # WxPusher
            if config.wxpusher_token and config.wxpusher_topic_ids:
                r = requests.post("https://wxpusher.zjiecode.com/api/send/message", json={
                    "appToken": config.wxpusher_token,
                    "content": f"<h3>{title}</h3><p>{content}</p>",
                    "contentType": 2,
                    "topicIds": config.wxpusher_topic_ids,
                }, timeout=10)
                results["wxpusher"] = r.json() if r.ok else {"error": r.status_code}

            return {"success": True, "results": results}
        except Exception as e:
            logger.error(f"推送发送失败: {e}")
            return {"success": False, "error": str(e)}
