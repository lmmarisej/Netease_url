"""通用任务管理器模块

提供线程安全的异步任务跟踪系统，支持：
- 任务创建、状态更新、查询
- 任务进度跟踪
- 任务历史保留（自动清理旧任务）
"""

import time
import threading
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"         # 等待中
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: str              # 任务类型（如 "download", "sync", "parse"）
    name: str                   # 显示名称
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0           # 进度 0-100
    message: str = ""           # 状态消息
    result: Any = None          # 结果数据
    error: str = ""             # 错误信息
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)  # 扩展字段


class TaskManager:
    """通用任务管理器（线程安全）"""

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
        self._lock = threading.Lock()
        self._tasks: Dict[str, TaskInfo] = {}
        self._max_history = 100  # 最多保留 100 个任务

    def create_task(self, task_type: str, name: str, **extra) -> TaskInfo:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        task = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            name=name,
            extra=extra
        )
        with self._lock:
            self._tasks[task_id] = task
            self._cleanup_old()
        return task

    def update_task(self, task_id: str, **kwargs) -> Optional[TaskInfo]:
        """更新任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = time.time()
            return task

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取单个任务"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_tasks(self, task_type: str = None, status: str = None, limit: int = 50) -> List[TaskInfo]:
        """获取任务列表，支持按类型和状态筛选，按创建时间倒序"""
        with self._lock:
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            if status:
                tasks = [t for t in tasks if t.status.value == status]
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]

    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def clear_completed(self) -> int:
        """清理已完成/失败/取消的任务"""
        with self._lock:
            to_remove = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in to_remove:
                del self._tasks[tid]
            return len(to_remove)

    def _cleanup_old(self):
        """保留最近的任务，删除旧的已完成任务"""
        if len(self._tasks) <= self._max_history:
            return
        completed = [
            (tid, t) for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]
        completed.sort(key=lambda x: x[1].created_at)
        excess = len(self._tasks) - self._max_history
        for tid, _ in completed[:excess]:
            del self._tasks[tid]

    def task_to_dict(self, task: TaskInfo) -> dict:
        """将任务转为可序列化的字典"""
        return {
            'task_id': task.task_id,
            'task_type': task.task_type,
            'name': task.name,
            'status': task.status.value,
            'progress': task.progress,
            'message': task.message,
            'error': task.error,
            'created_at': task.created_at,
            'updated_at': task.updated_at,
            'extra': task.extra
        }


# 全局单例
task_manager = TaskManager()
