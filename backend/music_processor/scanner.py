"""主流程 — 递归扫描 → 特征提取 → 事务内持久化。"""

import sys
import traceback
from pathlib import Path

from . import config
from . import database
from . import features as feats
from . import metadata as meta_mod
from . import panns
from . import persistence


def scan_and_process(
    music_folder: str,
    db_path: Path,
    username: str = "admin",
) -> None:
    """递归扫描 → 特征提取 → 事务内持久化。"""
    folder = Path(music_folder)
    if not folder.exists():
        print(f"[错误] 音乐文件夹不存在: {music_folder}")
        sys.exit(1)

    audio_files: list[Path] = []
    for ext in config.SUPPORTED_EXTENSIONS:
        audio_files.extend(folder.rglob(f"*{ext}"))
        audio_files.extend(folder.rglob(f"*{ext.upper()}"))
    audio_files = sorted(set(audio_files))

    if not audio_files:
        print(f"[提示] 未找到支持的音频文件 "
              f"({'/'.join(config.SUPPORTED_EXTENSIONS)})")
        return

    print(f"\n{'=' * 60}")
    print(f"  音乐特征处理器 — Music Feature Processor")
    print(f"{'=' * 60}")
    print(f"  扫描目录 : {music_folder}")
    print(f"  发现文件 : {len(audio_files)} 首")
    print(f"  数据库   : {db_path}")
    print(f"{'=' * 60}\n")

    conn = database.init_database(db_path)

    # 预加载已入库 file_path
    existing = set()
    try:
        cur = conn.execute("SELECT file_path FROM music_tracks")
        existing = {row[0] for row in cur.fetchall()}
    except Exception:
        pass

    success_count = 0
    skip_count = 0
    fail_count = 0

    for idx, file_path in enumerate(audio_files, 1):
        abs_path = str(file_path.resolve())
        rel_path = str(file_path.relative_to(folder)
                       if folder in file_path.parents else file_path)

        if abs_path in existing:
            print(f"[{idx:>4}/{len(audio_files)}] {rel_path}  (已存在，跳过)")
            skip_count += 1
            continue

        print(f"[{idx:>4}/{len(audio_files)}] {rel_path}")

        try:
            meta     = meta_mod.extract_metadata(abs_path)
            features = feats.extract_features(abs_path)
            if features is None:
                fail_count += 1
                continue

            lyrics = meta_mod.extract_lyrics(abs_path)

            # PANNs（独立异常保护）
            panns_tags: list[dict] = []
            try:
                panns_tags = panns.extract_panns_tags(abs_path)
            except Exception:
                print(f"  [PANNs] 跳过: {traceback.format_exc(limit=1)}")

            # 事务内原子写入
            scores = persistence.persist_track(
                conn, abs_path, meta, features, lyrics,
                panns_tags, username,
            )
            conn.commit()
            existing.add(abs_path)

            # 打印
            s_tempo, s_energy, s_bright, s_rhythm_v, s_tonal, \
                s_contrast, s_sentiment, pts = scores
            print(f"       → 速度:{s_tempo:>3}  能量:{s_energy:>3}  "
                  f"明亮:{s_bright:>3}  节奏:{s_rhythm_v:>3}  "
                  f"音调:{s_tonal:>3}")
            print(f"         起伏:{s_contrast:>3}  情感:{s_sentiment:>3}",
                  end="")
            if pts:
                top = pts[:config.PANNS_MAX_TOP_TAGS]
                tag_str = "  ".join(
                    f"{t['tag_name']}({t['confidence']})" for t in top
                )
                print(f"  🏷 {tag_str}")
            else:
                print()
            success_count += 1

        except Exception:
            print(f"  [异常] 处理文件时出错: {abs_path}")
            traceback.print_exc()
            conn.rollback()
            fail_count += 1

    conn.close()

    print(f"\n{'=' * 60}")
    print(f"  处理完成！")
    print(f"  新增: {success_count}  跳过: {skip_count}  "
          f"失败: {fail_count}  总计: {len(audio_files)}")
    print(f"  数据已写入: {db_path}")
    print(f"{'=' * 60}\n")
