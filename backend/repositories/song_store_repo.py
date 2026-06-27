"""
song_store_repo.py — 内容寻址共享存储层 (Content-Addressed Storage)
====================================================================
实现音乐文件的去重存储：
  - 共享目录 downloads/_store/{hash[:2]}/{hash}.{ext}
  - _store_index.json: hash → {title, artist, size, ext, ref_count}
  - 线程安全（threading.Lock）
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger("song_store")

# ────────────────────────── 路径常量 ──────────────────────────

_STORE_DIR_NAME = "_store"
_INDEX_FILE_NAME = "_store_index.json"

# 项目根目录（backend/ 的父目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_STORE_DIR = _PROJECT_ROOT / "downloads" / _STORE_DIR_NAME


class SongStoreRepo:
    """
    内容寻址歌曲存储仓库。

    共享目录结构:
      downloads/_store/
        ├── a1/
        │   └── a1b2c3d4...ff.mp3
        ├── b2/
        │   └── b2c3d4e5...aa.flac
        └── _store_index.json

    _store_index.json 格式:
      {
        "a1b2c3d4...ff": {
          "title": "晴天",
          "artist": "周杰伦",
          "size": 10485760,
          "ext": "mp3",
          "ref_count": 3
        }
      }
    """

    def __init__(self, store_dir: Optional[str] = None):
        self.store_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_dir / _INDEX_FILE_NAME
        self._lock = threading.Lock()
        self._index: Dict[str, dict] = {}
        self._load_index()

    # ═══════════════ 索引管理 ═══════════════

    def _load_index(self) -> None:
        """从磁盘加载索引文件"""
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                logger.info(f"已加载 {len(self._index)} 条存储索引")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"索引文件损坏，重建空索引: {e}")
                self._index = {}
        else:
            self._index = {}

    def _save_index(self) -> None:
        """原子写入索引文件（先写 .tmp 再 rename）"""
        tmp_path = self.index_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.index_path)
        except Exception as e:
            logger.error(f"保存索引失败: {e}")
            raise

    # ═══════════════ 核心操作 ═══════════════

    @staticmethod
    def compute_md5(file_path: Path, chunk_size: int = 8192) -> str:
        """计算文件的 MD5 哈希"""
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def has_content(self, content_hash: str) -> bool:
        """检查 _store 中是否已存在此哈希的文件"""
        with self._lock:
            return content_hash in self._index

    def resolve_path(self, content_hash: str, ext: str = "mp3") -> Path:
        """
        根据哈希和扩展名返回 _store 中的物理路径。

        示例: resolve_path("a1b2c3...ff", "mp3") → _store/a1/a1b2c3...ff.mp3
        """
        prefix = content_hash[:2]
        sub_dir = self.store_dir / prefix
        return sub_dir / f"{content_hash}.{ext}"

    def atomic_move(
        self,
        src_path: Path,
        content_hash: str,
        ext: str,
        metadata: Optional[Dict] = None,
    ) -> Tuple[Path, bool]:
        """
        原子移动文件到 _store。

        Args:
            src_path: 源文件路径
            content_hash: 文件 MD5 哈希
            ext: 扩展名（不含点，如 "mp3"）
            metadata: 可选的 {title, artist, size} 字典

        Returns:
            (目标路径, 是否为新增)
            - True: 文件首次写入 _store
            - False: _store 中已存在（跳过移动，src 可删除）
        """
        with self._lock:
            if content_hash in self._index:
                self._index[content_hash]["ref_count"] += 1
                self._save_index()
                dest = self.resolve_path(content_hash, ext)
                logger.info(f"去重命中: {content_hash[:12]}..., ref={self._index[content_hash]['ref_count']}")
                return dest, False

            # 首次存储
            dest = self.resolve_path(content_hash, ext)
            dest.parent.mkdir(parents=True, exist_ok=True)

            if not dest.exists():
                shutil.move(str(src_path), str(dest))
            else:
                # 极端情况：哈希冲突（几乎不可能）直接覆盖
                logger.warning(f"哈希冲突? 目标已存在: {dest}")
                src_path.unlink(missing_ok=True)

            # 更新索引
            self._index[content_hash] = {
                "title": (metadata or {}).get("title", ""),
                "artist": (metadata or {}).get("artist", ""),
                "size": (metadata or {}).get("size", dest.stat().st_size),
                "ext": ext,
                "ref_count": 1,
            }
            self._save_index()
            logger.info(f"新存储: {content_hash[:12]}... → {dest.relative_to(self.store_dir)}")
            return dest, True

    def get_stats(self) -> Dict:
        """获取存储统计（总大小、文件数、去重节省空间）"""
        with self._lock:
            total_files = len(self._index)
            total_size = sum(v.get("size", 0) for v in self._index.values())
            total_refs = sum(v.get("ref_count", 1) for v in self._index.values())
            # 节省空间 = (引用次数 - 1) × 文件大小 的总和
            saved = sum(
                v.get("size", 0) * (v.get("ref_count", 1) - 1)
                for v in self._index.values()
            )
            return {
                "total_files": total_files,
                "total_size": total_size,
                "total_size_mb": round(total_size / 1048576, 2),
                "total_refs": total_refs,
                "saved_size": saved,
                "saved_size_mb": round(saved / 1048576, 2),
                "dedup_ratio": round(total_refs / total_files, 2) if total_files else 0,
            }


# ────────────────────────── 模块级单例 ──────────────────────────

_store_instance: Optional[SongStoreRepo] = None


def get_song_store() -> SongStoreRepo:
    """获取 SongStoreRepo 单例"""
    global _store_instance
    if _store_instance is None:
        _store_instance = SongStoreRepo()
    return _store_instance
