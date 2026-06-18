"""
Music Feature Processor — 本地音乐特征提取、评分与 SQLite 持久化。

模块结构:
    config.py      全局配置常量
    utils.py       辅助工具 (clamp_and_scale)
    features.py    librosa 声学特征提取
    metadata.py    mutagen 元数据/歌词提取
    sentiment.py   snownlp 歌词情感分析
    scoring.py     6 大评分维度映射
    panns.py       PANNs CNN14 AI 标签识别
    database.py    SQLite 四表初始化
    persistence.py 事务内持久化流水线
    scanner.py     主流程扫描编排
"""

from .config import (
    MUSIC_FOLDER, USERNAME, DB_PATH,
)
from .scanner import scan_and_process
from .database import init_database

__all__ = [
    "MUSIC_FOLDER", "USERNAME", "DB_PATH",
    "scan_and_process", "init_database",
]
