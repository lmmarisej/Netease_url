"""
设置路由：下载配置、通用设置
"""

import json
from pathlib import Path

from flask import request

from backend.api_core import APIResponse
from backend.event_bus import EventType, fire_event
from backend.auth import get_current_user


def register_settings_routes(app, api_service, config):
    """注册设置相关路由"""

    @app.route('/api/settings', methods=['GET'])
    def get_settings():
        try:
            return APIResponse.success({
                'downloads_dir': config.downloads_dir,
                'download_save_local': config.download_save_local,
                'download_browser': config.download_browser,
                'download_default_quality': getattr(config, 'download_default_quality', 'lossless'),
                'download_quality_in_filename': getattr(config, 'download_quality_in_filename', True),
                'download_lyric_save_lrc': getattr(config, 'download_lyric_save_lrc', True),
            }, "获取配置成功")
        except Exception as e:
            return APIResponse.error(f"获取配置失败: {str(e)}", 500)

    @app.route('/api/settings', methods=['POST'])
    def save_settings():
        try:
            from backend.main import _get_user_settings_path
            data = api_service._safe_get_request_data()

            if 'downloads_dir' in data:
                config.downloads_dir = data['downloads_dir']
            if 'download_save_local' in data:
                config.download_save_local = str(data['download_save_local']).lower() in ('true', '1', 'yes')
            if 'download_browser' in data:
                config.download_browser = str(data['download_browser']).lower() in ('true', '1', 'yes')
            if 'download_default_quality' in data:
                config.download_default_quality = data['download_default_quality']
            if 'download_quality_in_filename' in data:
                config.download_quality_in_filename = str(data['download_quality_in_filename']).lower() in ('true', '1', 'yes')
            if 'download_lyric_save_lrc' in data:
                config.download_lyric_save_lrc = str(data['download_lyric_save_lrc']).lower() in ('true', '1', 'yes')

            settings_path = Path(_get_user_settings_path())
            current = {}
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    current = json.load(f)
            current['downloads_dir'] = config.downloads_dir
            current['download_save_local'] = config.download_save_local
            current['download_browser'] = config.download_browser
            current['download_default_quality'] = getattr(config, 'download_default_quality', 'lossless')
            current['download_quality_in_filename'] = getattr(config, 'download_quality_in_filename', True)
            current['download_lyric_save_lrc'] = getattr(config, 'download_lyric_save_lrc', True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(current, f, ensure_ascii=False, indent=2)

            fire_event(EventType.SETTINGS_UPDATED, {
                'downloads_dir': config.downloads_dir,
                'download_save_local': config.download_save_local,
                'download_browser': config.download_browser,
            }, source='api')

            return APIResponse.success({
                'downloads_dir': config.downloads_dir,
                'download_save_local': config.download_save_local,
                'download_browser': config.download_browser,
                'download_default_quality': getattr(config, 'download_default_quality', 'lossless'),
                'download_quality_in_filename': getattr(config, 'download_quality_in_filename', True),
                'download_lyric_save_lrc': getattr(config, 'download_lyric_save_lrc', True),
            }, "配置保存成功")
        except Exception as e:
            return APIResponse.error(f"保存配置失败: {str(e)}", 500)
