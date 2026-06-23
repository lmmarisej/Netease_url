"""
migrate_storage.py — 存量文件迁移脚本
=====================================
将 downloads/{user}/ 下的音频文件迁移到 CAS 共享存储 (_store)。

用法:
    # 预览（不实际移动）
    python backend/migrate_storage.py --dry-run

    # 迁移全部用户
    python backend/migrate_storage.py

    # 仅迁移指定用户
    python backend/migrate_storage.py --user admin

    # 查看统计
    python backend/migrate_storage.py --stats
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保 backend/ 在 Python 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.song_storage import (
    SongStorageService,
    ensure_user_song_table,
)


def main():
    parser = argparse.ArgumentParser(description="音乐文件 CAS 存储迁移工具")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际移动文件")
    parser.add_argument("--user", type=str, default=None, help="仅迁移指定用户")
    parser.add_argument("--stats", action="store_true", help="仅显示存储统计")
    args = parser.parse_args()

    # 确保表存在
    ensure_user_song_table()

    service = SongStorageService()

    if args.stats:
        s = service.get_store_stats()
        print("\n📊 CAS 存储统计:")
        print(f"  文件数:       {s['total_files']}")
        print(f"  总大小:       {s['total_size_mb']} MB")
        print(f"  引用次数:     {s['total_refs']}")
        print(f"  节省空间:     {s['saved_size_mb']} MB")
        print(f"  去重比:       {s['dedup_ratio']}x")
        return

    action = "预览" if args.dry_run else "迁移"
    target = args.user or "所有用户"
    print(f"\n🔄 {action}模式: {target}")

    result = service.migrate_existing_files(
        dry_run=args.dry_run,
        target_username=args.user,
    )

    print(f"\n✅ 完成:")
    print(f"  新存储:       {result['migrated']} 个文件")
    if args.dry_run:
        print(f"  已存在(跳过): {result['skipped']} 个")
        print(f"  预计节省:     {result['saved_bytes'] / 1048576:.1f} MB")
    if result["errors"]:
        print(f"  错误:         {len(result['errors'])}")
        for err in result["errors"][:5]:
            print(f"    - {err}")


if __name__ == "__main__":
    main()
