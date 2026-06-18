#!/usr/bin/env python3
"""
Music Feature Processor — 薄封装入口。

直接运行:
    cd backend && python music_processor.py

或作为模块运行:
    cd backend && python -m music_processor

依赖安装:
    pip install librosa soundfile mutagen numpy pandas snownlp torch panns-inference
"""
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from music_processor import MUSIC_FOLDER, DB_PATH, USERNAME, scan_and_process

if __name__ == "__main__":
    scan_and_process(MUSIC_FOLDER, DB_PATH, USERNAME)
