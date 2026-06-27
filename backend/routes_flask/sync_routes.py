"""
同步配置路由
"""

import traceback

from flask import request

from backend.api_core import APIResponse
from backend.event_bus import EventType, fire_event
from backend.playlist_sync import get_sync_service


def register_sync_routes(app, api_service, config):
    """注册同步相关路由"""

    @app.route('/api/sync/config', methods=['GET'])
    def get_sync_config():
        try:
            from backend.main import load_sync_config_from_file
            file_config = load_sync_config_from_file()
            if file_config:
                config_data = file_config
            else:
                config_data = {
                    'enable_sync': config.enable_sync,
                    'playlist_ids': config.playlist_ids,
                    'sync_quality': config.sync_quality,
                    'sync_interval': config.sync_interval,
                    'cron_expression': config.cron_expression or '',
                    'sync_full_delete': getattr(config, 'sync_full_delete', False),
                    'sync_dedup_files': getattr(config, 'sync_dedup_files', False),
                }
            return APIResponse.success(config_data, "获取同步配置成功")
        except Exception as e:
            return APIResponse.error(f"获取同步配置失败: {str(e)}", 500)

    @app.route('/api/sync/config', methods=['POST'])
    def save_sync_config():
        try:
            data = api_service._safe_get_request_data()
            if api_service.reload_sync_config(data):
                fire_event(EventType.SYNC_CONFIG_UPDATED, {
                    'enable_sync': data.get('enable_sync', False),
                    'playlist_count': len(data.get('playlist_ids', [])),
                }, source='api')
                return APIResponse.success({'message': '配置已保存，同步服务已更新'}, "配置保存成功")
            return APIResponse.error("配置保存失败", 500)
        except Exception as e:
            return APIResponse.error(f"保存同步配置失败: {str(e)}", 500)

    @app.route('/api/sync/status', methods=['GET'])
    def get_sync_status():
        try:
            sync_service = get_sync_service()
            if not sync_service:
                from backend.main import load_sync_config_from_file
                file_config = load_sync_config_from_file()
                return APIResponse.success({
                    'service_running': False, 'job_count': 0,
                    'config': {
                        'playlist_ids': file_config.get('playlist_ids', config.playlist_ids),
                        'quality': file_config.get('sync_quality', config.sync_quality),
                        'sync_interval': file_config.get('sync_interval', config.sync_interval),
                        'cron_expression': file_config.get('cron_expression', config.cron_expression or ''),
                        'download_dir': str(config.downloads_dir),
                    }
                }, "同步服务未运行")
            status = sync_service.get_sync_status()
            return APIResponse.success(status, "获取同步状态成功")
        except Exception as e:
            return APIResponse.error(f"获取同步状态失败: {str(e)}", 500)

    @app.route('/api/sync/now', methods=['POST'])
    def trigger_sync_now():
        try:
            sync_service = get_sync_service()
            if not sync_service:
                from backend.main import load_sync_config_from_file
                file_config = load_sync_config_from_file()
                if file_config.get('enable_sync') and file_config.get('playlist_ids'):
                    api_service.reload_sync_config(file_config)
                    sync_service = get_sync_service()
            if not sync_service:
                return APIResponse.error("同步服务未启用，请先在配置页保存同步配置", 400)

            results = sync_service.sync_all_playlists()
            success_count = sum(1 for r in results if r.get('success'))
            fail_count = len(results) - success_count
            total_synced = sum(r.get('synced_count', 0) for r in results)
            errors = [{'playlist_id': r.get('playlist_id', ''), 'error': r.get('error', '未知错误')}
                      for r in results if not r.get('success')]

            return APIResponse.success({
                'success_count': success_count, 'fail_count': fail_count,
                'total_synced': total_synced, 'errors': errors,
            }, f"同步完成: 成功 {success_count}/{len(results)}, 下载 {total_synced} 首")
        except Exception as e:
            return APIResponse.error(f"触发同步失败: {str(e)}", 500)
