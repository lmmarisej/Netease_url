"""
Flask 路由模块 — 依赖注入模式

各模块导出 register_xxx_routes(app, api_service, ...) 函数。
调用 register_all_routes(app, api_service, config, operation_logger, _PROJECT_ROOT) 统一注册所有路由。
"""

from .auth_routes import register_auth_routes
from .music_routes import register_music_routes
from .download_routes import register_download_routes
from .lyrics_routes import register_lyrics_routes
from .sync_routes import register_sync_routes
from .cookie_routes import register_cookie_routes
from .taste_routes import register_taste_routes
from .system_routes import register_system_routes
from .settings_routes import register_settings_routes
from .file_routes import register_file_routes
from .v3_routes import register_v3_routes


def register_all_routes(app, api_service, config, operation_logger, _PROJECT_ROOT):
    """向 Flask app 统一注册所有路由模块"""
    register_auth_routes(app, api_service)
    register_music_routes(app, api_service, config, operation_logger, _PROJECT_ROOT)
    register_download_routes(app, api_service, config, operation_logger, _PROJECT_ROOT)
    register_lyrics_routes(app, api_service, config, _PROJECT_ROOT)
    register_sync_routes(app, api_service, config)
    register_cookie_routes(app, api_service, config)
    register_taste_routes(app, api_service, _PROJECT_ROOT)
    register_system_routes(app, api_service, config, _PROJECT_ROOT)
    register_settings_routes(app, api_service, config)
    register_file_routes(app, api_service, _PROJECT_ROOT)
    register_v3_routes(app, api_service, _PROJECT_ROOT)
