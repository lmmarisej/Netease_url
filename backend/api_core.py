"""
api_core.py — 从 main.py 提取的核心类：APIConfig, APIResponse, MusicAPIService
语义完全不变。
"""
import logging
import time
import json
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from flask import request

# _PROJECT_ROOT 由调用方注入
_PROJECT_ROOT = None

def set_project_root(path: Path):
    global _PROJECT_ROOT
    _PROJECT_ROOT = path


@dataclass
class APIConfig:
    """API配置类"""
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False
    downloads_dir: str = 'downloads'
    download_save_local: bool = False
    download_browser: bool = True
    max_file_size: int = 500 * 1024 * 1024
    request_timeout: int = 30
    log_level: str = 'INFO'
    cors_origins: str = '*'
    enable_sync: bool = False
    playlist_ids: List[str] = None
    sync_quality: str = 'lossless'
    sync_interval: int = 3600
    cron_expression: str = None
    download_lyric_save_lrc: bool = True
    sync_full_delete: bool = False
    sync_dedup_files: bool = False

    def __post_init__(self):
        if self.playlist_ids is None:
            self.playlist_ids = []


class APIResponse:
    """API响应工具类"""

    @staticmethod
    def success(data: Any = None, message: str = 'success', status_code: int = 200) -> Tuple[Dict[str, Any], int]:
        response = {
            'status': status_code,
            'success': True,
            'message': message
        }
        if data is not None:
            response['data'] = data
        return response, status_code

    @staticmethod
    def error(message: str, status_code: int = 400, error_code: str = None) -> Tuple[Dict[str, Any], int]:
        response = {
            'status': status_code,
            'success': False,
            'message': message
        }
        if error_code:
            response['error_code'] = error_code
        return response, status_code
