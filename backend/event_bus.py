"""事件总线模块

提供项目级事件发布/订阅系统，支持：
- 全局事件枚举定义
- 线程安全的事件发布/订阅
- 通配符事件匹配
- 事件数据传递
- 与消息推送系统集成
"""

import threading
import time
import logging
from enum import Enum
from typing import Dict, List, Callable, Any, Optional, Set, Union
from dataclasses import dataclass, field


class EventType(Enum):
    """项目事件类型枚举

    按业务领域分类，每个事件具有唯一标识，可在配置中关联消息推送。
    """

    # ==================== 服务生命周期 ====================
    SERVER_STARTED = "server.started"           # 服务启动完成
    SERVER_STOPPED = "server.stopped"           # 服务即将停止

    # ==================== API 操作事件 ====================
    SONG_INFO_FETCHED = "song.info_fetched"     # 歌曲信息获取成功
    SEARCH_PERFORMED = "search.performed"       # 搜索操作完成
    PLAYLIST_FETCHED = "playlist.fetched"       # 歌单详情获取成功
    ALBUM_FETCHED = "album.fetched"             # 专辑详情获取成功

    # ==================== 下载生命周期 ====================
    DOWNLOAD_STARTED = "download.started"       # 下载任务开始
    DOWNLOAD_PROGRESS = "download.progress"     # 下载进度更新
    DOWNLOAD_COMPLETED = "download.completed"   # 下载完成
    DOWNLOAD_FAILED = "download.failed"         # 下载失败
    DOWNLOAD_QUALITY_DOWNGRADED = "download.quality_downgraded"  # 音质降级

    # ==================== 同步生命周期 ====================
    SYNC_STARTED = "sync.started"                       # 同步任务开始
    SYNC_PLAYLIST_STARTED = "sync.playlist_started"      # 单个歌单同步开始
    SYNC_SONG_DOWNLOADED = "sync.song_downloaded"        # 同步中单曲下载完成
    SYNC_PLAYLIST_COMPLETED = "sync.playlist_completed"  # 单个歌单同步完成
    SYNC_COMPLETED = "sync.completed"                   # 全部同步完成
    SYNC_FAILED = "sync.failed"                         # 同步任务失败

    # ==================== 任务管理事件 ====================
    TASK_CREATED = "task.created"        # 任务创建
    TASK_STARTED = "task.started"        # 任务开始执行
    TASK_PROGRESS = "task.progress"      # 任务进度更新
    TASK_COMPLETED = "task.completed"    # 任务完成
    TASK_FAILED = "task.failed"          # 任务失败
    TASK_CANCELLED = "task.cancelled"    # 任务取消

    # ==================== 配置变更事件 ====================
    COOKIE_UPDATED = "config.cookie_updated"           # Cookie 配置更新
    SETTINGS_UPDATED = "config.settings_updated"        # 通用设置更新
    SYNC_CONFIG_UPDATED = "config.sync_config_updated"  # 同步配置更新
    PUSH_CONFIG_UPDATED = "config.push_config_updated"  # 推送配置更新

    # ==================== 错误事件 ====================
    API_ERROR = "error.api"          # API 调用错误
    SYSTEM_ERROR = "error.system"    # 系统级错误


@dataclass
class Event:
    """事件数据对象

    Attributes:
        type: 事件类型（EventType 枚举值）
        data: 事件携带的数据（dict 或任意可序列化对象）
        timestamp: 事件发生时间戳（秒）
        source: 事件来源模块名
    """
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转为可序列化的字典"""
        return {
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp,
            'source': self.source
        }


# 事件处理器类型：接收 Event 对象
EventHandler = Callable[[Event], None]


class EventBus:
    """事件总线（线程安全单例）

    发布/订阅模式，支持：
    - 精确事件匹配：event.type == EventType.XXX
    - 通配符匹配：'sync.*' 匹配所有 sync. 开头的事件
    - 'download.*' 匹配所有下载相关事件
    - '*' 匹配所有事件

    使用示例::

        from event_bus import event_bus, EventType, Event

        def on_download_complete(event: Event):
            print(f"下载完成: {event.data}")

        event_bus.subscribe(EventType.DOWNLOAD_COMPLETED, on_download_complete)
        event_bus.emit(Event(EventType.DOWNLOAD_COMPLETED, {"song": "xxx"}))
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._rw_lock = threading.RLock()
        self._history: List[Event] = []
        self._max_history = 200
        self._logger = logging.getLogger('event_bus')

    def subscribe(self, event_type: Union[EventType, str], handler: EventHandler) -> None:
        """订阅事件

        Args:
            event_type: EventType 枚举值 或 通配符字符串（如 'sync.*', '*'）
            handler: 事件处理回调函数，接收 Event 对象
        """
        key = event_type.value if isinstance(event_type, EventType) else event_type
        with self._rw_lock:
            if key not in self._subscribers:
                self._subscribers[key] = []
            if handler not in self._subscribers[key]:
                self._subscribers[key].append(handler)
            self._logger.debug(f"事件订阅: key={key}, handler={handler.__name__}")

    def unsubscribe(self, event_type: Union[EventType, str], handler: EventHandler) -> None:
        """取消订阅

        Args:
            event_type: 订阅时使用的事件类型或通配符
            handler: 要移除的处理器
        """
        key = event_type.value if isinstance(event_type, EventType) else event_type
        with self._rw_lock:
            if key in self._subscribers and handler in self._subscribers[key]:
                self._subscribers[key].remove(handler)
                if not self._subscribers[key]:
                    del self._subscribers[key]
                self._logger.debug(f"取消订阅: key={key}")

    def unsubscribe_all(self, event_type: Optional[Union[EventType, str]] = None) -> None:
        """取消所有订阅（可指定事件类型）"""
        with self._rw_lock:
            if event_type is None:
                self._subscribers.clear()
            else:
                key = event_type.value if isinstance(event_type, EventType) else event_type
                self._subscribers.pop(key, None)

    def emit(self, event: Event) -> None:
        """发布事件（同步调用所有匹配的处理器）

        Args:
            event: 事件对象
        """
        event_value = event.type.value

        # 保存到历史
        with self._rw_lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        # 收集匹配的处理器
        matched_handlers: Set[EventHandler] = set()
        with self._rw_lock:
            for key, handlers in self._subscribers.items():
                if self._match_event(event_value, key):
                    matched_handlers.update(handlers)

        # 调用所有匹配的处理器（在锁外执行，避免死锁）
        for handler in matched_handlers:
            try:
                handler(event)
            except Exception as e:
                self._logger.error(
                    f"事件处理器异常: event={event_value}, "
                    f"handler={getattr(handler, '__name__', str(handler))}, error={e}"
                )

    def emit_async(self, event: Event) -> None:
        """异步发布事件（在独立线程中调用处理器）"""
        thread = threading.Thread(
            target=self.emit,
            args=(event,),
            daemon=True,
            name=f"event-{event.type.value}"
        )
        thread.start()

    @staticmethod
    def _match_event(event_value: str, pattern: str) -> bool:
        """事件匹配（支持通配符）

        规则：
        - 精确匹配：event_value == pattern
        - 后缀通配：'sync.*' 匹配 'sync.started', 'sync.completed' 等
        - 全匹配：'*' 匹配所有事件

        Args:
            event_value: 实际事件值，如 'download.completed'
            pattern: 订阅模式，如 'download.*' 或 '*'

        Returns:
            是否匹配
        """
        if pattern == '*':
            return True
        if pattern.endswith('.*'):
            prefix = pattern[:-2]
            return event_value.startswith(prefix + '.') or event_value == prefix
        return event_value == pattern

    def get_history(self, event_type: Optional[EventType] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        """获取事件历史（倒序）

        Args:
            event_type: 可选，筛选特定事件类型
            limit: 返回条数限制

        Returns:
            事件字典列表
        """
        with self._rw_lock:
            history = list(self._history)
            if event_type:
                history = [e for e in history if e.type == event_type]
            history.reverse()
            return [e.to_dict() for e in history[:limit]]

    def clear_history(self) -> None:
        """清空事件历史"""
        with self._rw_lock:
            self._history.clear()

    def get_subscribers_info(self) -> List[Dict[str, Any]]:
        """获取当前订阅信息"""
        with self._rw_lock:
            return [
                {
                    'pattern': key,
                    'handler_count': len(handlers)
                }
                for key, handlers in self._subscribers.items()
            ]


# 全局事件总线单例
event_bus = EventBus()


# ==================== 事件辅助函数 ====================

def create_event(event_type: EventType, data: Dict[str, Any] = None,
                 source: str = "") -> Event:
    """快捷创建事件对象"""
    return Event(
        type=event_type,
        data=data or {},
        source=source
    )


def fire_event(event_type: EventType, data: Dict[str, Any] = None,
               source: str = "", async_mode: bool = False) -> Event:
    """快捷发布事件

    Args:
        event_type: 事件类型
        data: 事件数据
        source: 来源模块
        async_mode: 是否异步发布

    Returns:
        创建的 Event 对象
    """
    event = create_event(event_type, data, source)
    if async_mode:
        event_bus.emit_async(event)
    else:
        event_bus.emit(event)
    return event


# ==================== 事件分类信息（供前端展示） ====================

EVENT_CATEGORIES = {
    "服务生命周期": [
        EventType.SERVER_STARTED,
        EventType.SERVER_STOPPED,
    ],
    "API 操作": [
        EventType.SONG_INFO_FETCHED,
        EventType.SEARCH_PERFORMED,
        EventType.PLAYLIST_FETCHED,
        EventType.ALBUM_FETCHED,
    ],
    "下载事件": [
        EventType.DOWNLOAD_STARTED,
        EventType.DOWNLOAD_PROGRESS,
        EventType.DOWNLOAD_COMPLETED,
        EventType.DOWNLOAD_FAILED,
        EventType.DOWNLOAD_QUALITY_DOWNGRADED,
    ],
    "同步事件": [
        EventType.SYNC_STARTED,
        EventType.SYNC_PLAYLIST_STARTED,
        EventType.SYNC_SONG_DOWNLOADED,
        EventType.SYNC_PLAYLIST_COMPLETED,
        EventType.SYNC_COMPLETED,
        EventType.SYNC_FAILED,
    ],
    "任务管理": [
        EventType.TASK_CREATED,
        EventType.TASK_STARTED,
        EventType.TASK_PROGRESS,
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
        EventType.TASK_CANCELLED,
    ],
    "配置变更": [
        EventType.COOKIE_UPDATED,
        EventType.SETTINGS_UPDATED,
        EventType.SYNC_CONFIG_UPDATED,
        EventType.PUSH_CONFIG_UPDATED,
    ],
    "错误事件": [
        EventType.API_ERROR,
        EventType.SYSTEM_ERROR,
    ],
}

EVENT_DISPLAY_NAMES = {
    EventType.SERVER_STARTED: "服务启动",
    EventType.SERVER_STOPPED: "服务停止",
    EventType.SONG_INFO_FETCHED: "歌曲信息获取",
    EventType.SEARCH_PERFORMED: "搜索操作",
    EventType.PLAYLIST_FETCHED: "歌单详情获取",
    EventType.ALBUM_FETCHED: "专辑详情获取",
    EventType.DOWNLOAD_STARTED: "下载开始",
    EventType.DOWNLOAD_PROGRESS: "下载进度",
    EventType.DOWNLOAD_COMPLETED: "下载完成",
    EventType.DOWNLOAD_FAILED: "下载失败",
    EventType.DOWNLOAD_QUALITY_DOWNGRADED: "音质降级",
    EventType.SYNC_STARTED: "同步开始",
    EventType.SYNC_PLAYLIST_STARTED: "歌单同步开始",
    EventType.SYNC_SONG_DOWNLOADED: "同步歌曲下载",
    EventType.SYNC_PLAYLIST_COMPLETED: "歌单同步完成",
    EventType.SYNC_COMPLETED: "同步完成",
    EventType.SYNC_FAILED: "同步失败",
    EventType.TASK_CREATED: "任务创建",
    EventType.TASK_STARTED: "任务开始",
    EventType.TASK_PROGRESS: "任务进度",
    EventType.TASK_COMPLETED: "任务完成",
    EventType.TASK_FAILED: "任务失败",
    EventType.TASK_CANCELLED: "任务取消",
    EventType.COOKIE_UPDATED: "Cookie 更新",
    EventType.SETTINGS_UPDATED: "设置更新",
    EventType.SYNC_CONFIG_UPDATED: "同步配置更新",
    EventType.PUSH_CONFIG_UPDATED: "推送配置更新",
    EventType.API_ERROR: "API 错误",
    EventType.SYSTEM_ERROR: "系统错误",
}


def get_events_catalog() -> List[Dict[str, Any]]:
    """获取完整事件目录（供 API 返回）"""
    catalog = []
    for category, events in EVENT_CATEGORIES.items():
        items = []
        for evt in events:
            items.append({
                'type': evt.value,
                'name': EVENT_DISPLAY_NAMES.get(evt, evt.value),
                'category': category,
            })
        catalog.append({
            'category': category,
            'events': items,
        })
    return catalog
