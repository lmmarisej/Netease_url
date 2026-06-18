#!/usr/bin/env python3
"""
=============================================================================
  Music Feature Processor — 本地音乐特征提取、评分与 SQLite 持久化脚本
=============================================================================

## 开源技术选型与依赖安装指南

本脚本依赖以下主流开源音频处理与数据处理库：

| 库名       | 用途                               | 开源协议     |
|------------|------------------------------------|-------------|
| librosa    | 音频解码、声学特征提取              | ISC License |
| soundfile  | 跨格式音频文件读写（librosa 后端）   | BSD-3       |
| mutagen    | 跨格式音频元数据（MP3/FLAC/M4A 标签）| GPL-2.0     |
| numpy      | 数值计算与矩阵运算                  | BSD-3       |
| pandas     | 结构化数据处理（可选，备用）         | BSD-3       |
| sqlite3    | Python 内置，轻量级数据库            | Public Domain |

### 一键安装命令

    pip install librosa soundfile mutagen numpy pandas

### 关于 MP3 解码的重要提示

librosa 依赖 audioread 和 soundfile 解码音频。在 Windows / macOS / Linux 上解码
MP3 格式时，强烈建议确保系统已安装 FFmpeg（开源音频/视频解码器）：

- **Windows:** 下载 FFmpeg (https://ffmpeg.org/download.html)，将 bin 目录加入 PATH
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` 或 `sudo dnf install ffmpeg`

安装后验证: `ffmpeg -version`

## 功能概述

1. 递归扫描指定文件夹下的 .mp3 / .flac / .wav / .m4a 音频文件
2. 通过 mutagen 提取元数据（歌名、歌手、专辑）
3. 通过 librosa 提取声学特征（仅加载前 60 秒以提升效率）
4. 将底层物理特征映射为 0–100 分的 5 大核心评分维度
5. 写入 SQLite 数据库 music_vault.db（UPSERT 逻辑，基于 file_path 唯一索引）

## 5 大评分维度说明

| 维度              | 英文名              | 底层特征             | 含义                       |
|-------------------|--------------------|----------------------|---------------------------|
| 速度律动          | score_tempo        | BPM (Tempo)          | 节奏快慢，BPM 越高分越高    |
| 能量爆发          | score_energy       | RMS Energy           | 响度/能量感               |
| 音色明亮          | score_brightness   | Spectral Centroid    | 频谱中心，越高越明亮       |
| 过零率/粗糙度      | score_rhythm       | Zero Crossing Rate   | 打击乐感和音色噪感         |
| 音调丰富度        | score_tonality     | MFCC (13 维均值)     | 情绪调性替代特征           |

## 使用方式

1. 修改下方 MUSIC_FOLDER 为你的本地音乐目录
2. 运行: python music_processor.py
=============================================================================
"""

import os
import sys
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np

# =============================================================================
# 全局配置 — 请根据你的实际路径修改
# =============================================================================
# 默认扫描项目下的 downloads 目录（相对脚本位置: backend/../downloads）
MUSIC_FOLDER = str((Path(__file__).resolve().parent.parent / "downloads"))
# MUSIC_FOLDER = r"E:\MyMusic"   # 示例：改为你的音乐文件夹路径

# 当前用户标识 — 用于标记这首音乐是谁喜欢的，后续可扩展多用户
USERNAME = "admin"
# =============================================================================

# 支持的音频扩展名
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a"}

# 数据库文件路径（存储在 config/ 目录下）
DB_PATH = Path(__file__).resolve().parent.parent / "config" / "music_vault.db"

# librosa 加载时长上限（秒），仅加载前 N 秒以提升效率
LOAD_DURATION_SEC = 60.0

# ─────────────────────────────────────────────────────────────────────────────
# 评分归一化边界（基于流行乐常见范围预设）
# ─────────────────────────────────────────────────────────────────────────────

# RMS Energy 归一化边界：低于 MIN 映射为 0，高于 MAX 映射为 100
ENERGY_RMS_MIN = 0.01
ENERGY_RMS_MAX = 0.30

# Spectral Centroid 归一化边界（Hz）：越低越低沉，越高越明亮
CENTROID_MIN_HZ = 200.0
CENTROID_MAX_HZ = 5000.0

# Zero Crossing Rate 归一化边界
ZCR_MIN = 0.01
ZCR_MAX = 0.25

# MFCC 均值归一化边界（13 维 MFCC 的全局均值通常在 -80 到 +30 左右）
MFCC_MEAN_MIN = -80.0
MFCC_MEAN_MAX = 30.0


# =============================================================================
# 辅助工具函数
# =============================================================================

def clamp_and_scale(value: float, vmin: float, vmax: float) -> int:
    """
    将 value 线性映射到 0–100 整数区间，超出 [vmin, vmax] 的部分会被截断。

    Args:
        value: 原始数值
        vmin:  归一化下界（<= vmin 映射为 0）
        vmax:  归一化上界（>= vmax 映射为 100）

    Returns:
        0–100 的整数分
    """
    if vmax <= vmin:
        return 50  # 防御性兜底
    clamped = max(vmin, min(vmax, value))
    scaled = (clamped - vmin) / (vmax - vmin) * 100.0
    return int(round(scaled))


# =============================================================================
# 声学特征提取（librosa）
# =============================================================================

def extract_features(file_path: str) -> dict | None:
    """
    使用 librosa 加载音频文件前 LOAD_DURATION_SEC 秒，提取以下特征：

    - tempo (BPM)
    - RMS Energy (均值)
    - Spectral Centroid (均值)
    - Spectral Rolloff (均值)
    - Zero Crossing Rate (均值)
    - MFCC (13 维均值向量)

    Args:
        file_path: 音频文件绝对路径

    Returns:
        dict: 包含上述特征的字典，若失败返回 None
    """
    # 延迟导入 librosa，方便在未安装时给出友好提示
    try:
        import librosa  # noqa: F811
    except ImportError:
        print("[错误] 未安装 librosa，请先执行: pip install librosa soundfile")
        return None

    try:
        # ── 加载音频（仅前 N 秒，mono 单声道） ──
        y, sr = librosa.load(
            file_path,
            sr=None,              # 保留原始采样率
            mono=True,
            duration=LOAD_DURATION_SEC,
        )

        if len(y) == 0:
            print(f"  [警告] 音频数据为空: {file_path}")
            return None

        # ── Tempo (BPM) — librosa 0.10+ 返回 numpy 数组，用 .item() 提取标量 ──
        tempo_arr, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.asarray(tempo_arr).flat[0]) if tempo_arr is not None else 0.0

        # ── RMS Energy (逐帧均方根能量 → 全局均值) ──
        rms = librosa.feature.rms(y=y)
        rms_mean = float(np.mean(rms))  # type: ignore[arg-type]

        # ── Spectral Centroid (频谱质心 → 全局均值) ──
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        centroid_mean = float(np.mean(centroid))  # type: ignore[arg-type]

        # ── Spectral Rolloff (频谱滚降点 → 全局均值) ──
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        rolloff_mean = float(np.mean(rolloff))  # type: ignore[arg-type]

        # ── Zero Crossing Rate (过零率 → 全局均值) ──
        zcr = librosa.feature.zero_crossing_rate(y)
        zcr_mean = float(np.mean(zcr))  # type: ignore[arg-type]

        # ── MFCC (13 维梅尔倒谱系数 → 逐维度均值 → 全局均值) ──
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_means = np.mean(mfcc, axis=1)  # shape (13,)
        mfcc_overall_mean = float(np.mean(mfcc_means))  # type: ignore[arg-type]

        return {
            "tempo": round(tempo, 2),
            "rms_mean": round(rms_mean, 6),
            "centroid_mean": round(centroid_mean, 2),
            "rolloff_mean": round(rolloff_mean, 2),
            "zcr_mean": round(zcr_mean, 6),
            "mfcc_mean": round(mfcc_overall_mean, 2),
        }

    except Exception:
        print(f"  [错误] 音频特征提取失败: {file_path}")
        traceback.print_exc()
        return None


# =============================================================================
# 元数据提取（mutagen）
# =============================================================================

def extract_metadata(file_path: str) -> dict[str, str]:
    """
    使用 mutagen 解析音频文件标签，返回 {title, artist, album}。

    支持 MP3 (ID3)、FLAC (VorbisComment)、MP4/M4A (iTunes-style)。

    Args:
        file_path: 音频文件绝对路径

    Returns:
        dict: {"title": ..., "artist": ..., "album": ...}，缺失字段填充 "未知"
    """
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        print("[错误] 未安装 mutagen，请先执行: pip install mutagen")
        return {"title": "未知", "artist": "未知", "album": "未知"}

    meta = {"title": "未知", "artist": "未知", "album": "未知"}

    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is None:
            return meta

        # mutagen Easy 模式统一提供 list 类型的 tag 值
        if audio.get("title"):
            meta["title"] = str(audio["title"][0])
        if audio.get("artist"):
            meta["artist"] = str(audio["artist"][0])
        if audio.get("album"):
            meta["album"] = str(audio["album"][0])

        # 如果标签为空，回退到文件名（不含扩展名）
        if meta["title"] == "未知":
            meta["title"] = Path(file_path).stem

    except Exception:
        print(f"  [警告] 元数据读取失败，使用文件名回退: {file_path}")
        meta["title"] = Path(file_path).stem

    return meta


# =============================================================================
# 5 大评分维度映射函数 (0–100)
# =============================================================================

def score_tempo(tempo_bpm: float) -> int:
    """
    速度律动评分：
      BPM < 80   → 0–40  (慢节奏)
      BPM 80–120 → 40–70 (中速)
      BPM > 120  → 70–100(快节奏)
    """
    if tempo_bpm <= 0:
        return 0
    if tempo_bpm < 80:
        # 0..80 → 0..40（先线性映射再缩放到目标区间）
        ratio = tempo_bpm / 80.0
        return int(round(ratio * 40))
    elif tempo_bpm <= 120:
        # 80..120 → 40..70
        ratio = (tempo_bpm - 80) / 40.0
        return int(round(40 + ratio * 30))
    else:
        # 120..220 → 70..100（封顶 220 BPM）
        clamped = min(tempo_bpm, 220.0)
        ratio = (clamped - 120) / 100.0
        return int(round(70 + ratio * 30))


def score_energy(rms_mean: float) -> int:
    """
    能量爆发评分：对 RMS Energy 做 Min-Max 归一化到 0–100。

    RMS 越低 → 越轻柔（低分），越高 → 越响亮（高分）。
    边界 ENERGY_RMS_MIN / MAX 在脚本顶部可调。
    """
    return clamp_and_scale(rms_mean, ENERGY_RMS_MIN, ENERGY_RMS_MAX)


def score_brightness(centroid_mean: float) -> int:
    """
    音色明亮评分：对 Spectral Centroid (Hz) 做归一化。

    越低 → 低沉/暗淡（低分），越高 → 清脆/明亮（高分）。
    """
    return clamp_and_scale(centroid_mean, CENTROID_MIN_HZ, CENTROID_MAX_HZ)


def score_rhythm(zcr_mean: float) -> int:
    """
    过零率/粗糙度评分：Zero Crossing Rate 越高 → 打击感/噪感越强 → 得分越高。
    """
    return clamp_and_scale(zcr_mean, ZCR_MIN, ZCR_MAX)


def score_tonality(mfcc_overall_mean: float) -> int:
    """
    音调丰富度评分：基于 13 维 MFCC 全局均值的线性映射。

    MFCC 均值越高（越接近 0 或正值）通常代表频谱能量更集中于中高频，
    音调变化更丰富，得分越高。
    """
    return clamp_and_scale(mfcc_overall_mean, MFCC_MEAN_MIN, MFCC_MEAN_MAX)


# =============================================================================
# SQLite 数据库初始化
# =============================================================================

def init_database(db_path: Path) -> sqlite3.Connection:
    """
    初始化 SQLite 数据库，创建 music_features 表（如果不存在）。

    (file_name, username) 组合设 UNIQUE 约束，同一用户不会重复解析同一文件。

    Args:
        db_path: 数据库文件路径

    Returns:
        sqlite3.Connection 对象
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")       # 提升并发写入性能
    conn.execute("PRAGMA foreign_keys=ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS music_features (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT,
            artist          TEXT,
            album           TEXT,
            file_name       TEXT NOT NULL,
            username        TEXT NOT NULL DEFAULT 'admin',
            score_tempo     INTEGER,
            score_energy    INTEGER,
            score_brightness INTEGER,
            score_rhythm    INTEGER,
            score_tonality  INTEGER,
            is_favorite     INTEGER DEFAULT 1,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_name, username)
        )
    """)

    # 联合索引：按用户名 + 文件名快速查找
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_user
        ON music_features(file_name, username)
    """)

    conn.commit()
    return conn


def upsert_record(conn: sqlite3.Connection, record: dict) -> None:
    """
    UPSERT（存在则更新，不存在则插入）一条音乐特征记录。

    基于 (file_name, username) 组合唯一性判断。

    Args:
        conn:   数据库连接
        record: 包含所有字段值的字典
    """
    sql = """
        INSERT INTO music_features
            (title, artist, album, file_name, username,
             score_tempo, score_energy, score_brightness,
             score_rhythm, score_tonality, is_favorite, created_at)
        VALUES
            (:title, :artist, :album, :file_name, :username,
             :score_tempo, :score_energy, :score_brightness,
             :score_rhythm, :score_tonality, :is_favorite, :created_at)
        ON CONFLICT(file_name, username) DO UPDATE SET
            title           = excluded.title,
            artist          = excluded.artist,
            album           = excluded.album,
            score_tempo     = excluded.score_tempo,
            score_energy    = excluded.score_energy,
            score_brightness= excluded.score_brightness,
            score_rhythm    = excluded.score_rhythm,
            score_tonality  = excluded.score_tonality,
            is_favorite     = excluded.is_favorite,
            created_at      = excluded.created_at
    """
    try:
        conn.execute(sql, record)
        conn.commit()
    except sqlite3.Error as e:
        print(f"  [数据库错误] 写入失败: {record.get('file_name')} — {e}")


# =============================================================================
# 主流程：扫描文件夹 → 提取特征 → 写入数据库
# =============================================================================

def scan_and_process(music_folder: str, db_path: Path, username: str = "admin") -> None:
    """
    扫描 music_folder 下所有支持的音频文件，逐一提取元数据与声学特征，
    计算 5 大评分维度，并 UPSERT 写入 SQLite 数据库。

    如果某文件已存在于数据库中（按 file_name + username 判断），
    则跳过解析，避免重复计算。

    Args:
        music_folder: 音乐文件夹路径
        db_path:      数据库文件路径
        username:     用户标识，标记这首音乐属于谁
    """
    folder = Path(music_folder)
    if not folder.exists():
        print(f"[错误] 音乐文件夹不存在: {music_folder}")
        sys.exit(1)

    # 收集所有支持的音频文件
    audio_files: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        audio_files.extend(folder.rglob(f"*{ext}"))
        audio_files.extend(folder.rglob(f"*{ext.upper()}"))

    # 去重（同一文件可能被不同大小写扩展名匹配两次）
    audio_files = sorted(set(audio_files))

    if not audio_files:
        print(f"[提示] 在 {music_folder} 中未找到支持的音频文件 "
              f"({'/'.join(SUPPORTED_EXTENSIONS)})")
        return

    print(f"\n{'='*60}")
    print(f"  音乐特征处理器 — Music Feature Processor")
    print(f"{'='*60}")
    print(f"  扫描目录 : {music_folder}")
    print(f"  发现文件 : {len(audio_files)} 首")
    print(f"  数据库   : {db_path}")
    print(f"{'='*60}\n")

    # 初始化数据库
    conn = init_database(db_path)

    # 预加载已入库的 (file_name, username) 集合，用于快速跳过
    existing = set()
    try:
        cur = conn.execute(
            "SELECT file_name FROM music_features WHERE username = ?", (username,)
        )
        existing = {row[0] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        # 表可能尚不存在或结构不匹配，忽略
        pass

    success_count = 0
    fail_count = 0
    skip_count = 0

    for idx, file_path in enumerate(audio_files, 1):
        rel_path = file_path.relative_to(folder) if folder in file_path.parents else file_path
        file_name = file_path.name  # 仅文件名，不含路径

        # ── 0. 跳过已存在的文件 ──
        if file_name in existing:
            print(f"[{idx:>4}/{len(audio_files)}] {rel_path}  (已存在，跳过)")
            skip_count += 1
            continue

        print(f"[{idx:>4}/{len(audio_files)}] {rel_path}")

        try:
            # ── 1. 提取元数据 ──
            meta = extract_metadata(str(file_path))

            # ── 2. 提取声学特征 ──
            features = extract_features(str(file_path))
            if features is None:
                fail_count += 1
                continue

            # ── 3. 映射为 5 大评分维度 ──
            s_tempo = score_tempo(features["tempo"])
            s_energy = score_energy(features["rms_mean"])
            s_bright = score_brightness(features["centroid_mean"])
            s_rhythm = score_rhythm(features["zcr_mean"])
            s_tonal = score_tonality(features["mfcc_mean"])

            # ── 4. 组装记录 ──
            record = {
                "title": meta["title"],
                "artist": meta["artist"],
                "album": meta["album"],
                "file_name": file_name,
                "username": username,
                "score_tempo": s_tempo,
                "score_energy": s_energy,
                "score_brightness": s_bright,
                "score_rhythm": s_rhythm,
                "score_tonality": s_tonal,
                "is_favorite": 1,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # ── 5. UPSERT 写入 ──
            upsert_record(conn, record)
            existing.add(file_name)  # 内存缓存也同步更新

            print(f"       → 速度:{s_tempo:>3}  能量:{s_energy:>3}  "
                  f"明亮:{s_bright:>3}  节奏:{s_rhythm:>3}  音调:{s_tonal:>3}")
            success_count += 1

        except Exception:
            print(f"  [异常] 处理文件时出错: {file_path}")
            traceback.print_exc()
            fail_count += 1

    conn.close()

    # ── 汇总报告 ──
    print(f"\n{'='*60}")
    print(f"  处理完成！")
    print(f"  新增: {success_count}  跳过: {skip_count}  失败: {fail_count}  总计: {len(audio_files)}")
    print(f"  数据已写入: {db_path}")
    print(f"{'='*60}\n")


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    scan_and_process(MUSIC_FOLDER, DB_PATH, USERNAME)
