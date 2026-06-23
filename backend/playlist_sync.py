"""定时任务调度器模块

提供网易云音乐歌单定时同步功能，包括：
- 定时同步指定歌单到本地
- 支持多种音质选择
- 自动下载新歌
- 同步日志记录

注意：核心逻辑已拆分至 services/playlist_sync.py、models/sync_config.py、
repositories/sync_history_repo.py。本文件保留向后兼容的重导出。
"""

# ── 向后兼容重导出（Router-Service-Repository 重构）──
from services.playlist_sync import PlaylistSyncService as _NewService
from models.sync_config import PlaylistSyncConfig
from repositories.sync_history_repo import SyncHistoryRepository

# 全局单例（保持原 API 兼容）
_sync_service_instance = None

def init_sync_service(config: PlaylistSyncConfig) -> _NewService:
    """初始化同步服务（工厂函数，保持原调用方式）"""
    global _sync_service_instance
    _sync_service_instance = _NewService(config)
    return _sync_service_instance

def get_sync_service() -> _NewService | None:
    """获取当前同步服务实例"""
    return _sync_service_instance

# 向后兼容别名
PlaylistSyncService = _NewService
