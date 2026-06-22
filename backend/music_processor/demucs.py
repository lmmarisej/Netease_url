"""Demucs 声源分离 — 后台异步提取人声主导度 & 重低音轰炸度。

调用 Meta Demucs CLI，在独立线程中完成分离→RMS 评分→DB 更新→缓存清理。
"""

import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from pathlib import Path

logger = logging.getLogger("music_api")


def analyze_demucs_async(
    track_id: int,
    file_path: str,
    db_path: str,
) -> None:
    """在独立 daemon 线程中启动 Demucs 分离流程。

    Args:
        track_id:   music_tracks 主键
        file_path:  音频文件绝对路径
        db_path:    SQLite 数据库路径
    """
    def _run():
        try:
            _run_demucs(track_id, file_path, db_path)
        except Exception:
            logger.error(
                f"[Demucs] 后台线程异常 track_id={track_id}: "
                f"{__import__('traceback').format_exc()}"
            )

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    logger.info(f"[Demucs] 已加入后台异步精细化解剖队列: track_id={track_id}")


def _run_demucs(track_id: int, file_path: str, db_path: str) -> None:
    """核心分离流程：subprocess 调用 demucs → RMS 评分 → DB 更新 → 清理。"""
    start_time = time.time()

    # 1. 创建临时输出目录
    out_dir = tempfile.mkdtemp(prefix="demucs_")
    model = "htdemucs"  # Hybrid Transformer Demucs

    try:
        # 2. 双 stem 模式（人声+伴奏，速度快）
        logger.info(
            f"[Demucs] 开始分离 track_id={track_id}, model={model}"
        )
        cmd = [
            "demucs",
            "--two-stems", "vocals",
            "-j", "2",
            "-n", model,
            "-o", out_dir,
            file_path,
        ]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟
                check=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError,
                FileNotFoundError) as e:
            logger.warning(
                f"[Demucs] 双 stem 分离失败 track_id={track_id}: {e}"
            )
            _cleanup_cache(out_dir, track_id)
            raise

        # 3. 定位分离结果文件
        stem = Path(os.path.basename(file_path))
        vocals_path = (
            Path(out_dir) / model / stem.stem / "vocals.wav"
        )
        accompaniment_path = (
            Path(out_dir) / model / stem.stem / "no_vocals.wav"
        )

        if not vocals_path.exists():
            logger.error(
                f"[Demucs] 未找到分离结果: {vocals_path}"
            )
            _cleanup_cache(out_dir, track_id)
            raise FileNotFoundError(f"Vocals stem missing: {vocals_path}")

        # 4. RMS 评分
        try:
            import soundfile as sf
        except ImportError:
            logger.warning(
                "[Demucs] soundfile 未安装，跳过 RMS 评分"
            )
            _cleanup_cache(out_dir, track_id)
            return

        vocal_score = _compute_rms_score(vocals_path, "vocal")
        accomp_score = _compute_rms_score(accompaniment_path, "accomp")

        # 重低音轰炸度 ≈ 伴奏 RMS 分（鼓/bass 集中在伴奏中）
        sub_bass_score = accomp_score

        logger.info(
            f"[Demucs] track_id={track_id} "
            f"人声主导度={vocal_score} 重低音轰炸度={sub_bass_score}"
        )

        # 5. 写回数据库
        _update_db_scores(track_id, vocal_score, sub_bass_score, db_path)

        elapsed = time.time() - start_time
        logger.info(
            f"[Demucs] track_id={track_id} 完成, 耗时 {elapsed:.1f}s"
        )

    except Exception:
        logger.error(
            f"[Demucs] track_id={track_id} 异常: "
            f"{__import__('traceback').format_exc()}"
        )
    finally:
        _cleanup_cache(out_dir, track_id)


def _compute_rms_score(wav_path: Path, label: str = "") -> int:
    """从 60s 处读取 30s 高潮段，RMS → 0-100 分。

    短文件自动回退到 25% 位置。
    """
    import numpy as np
    import soundfile as sf

    try:
        info = sf.info(str(wav_path))
        sr = info.samplerate
        total_frames = info.frames

        # 短文件回退到 25% 位置
        if total_frames / sr < 90:
            offset = int(total_frames * 0.25)
        else:
            offset = 60 * sr  # 从 60s 处开始

        chunk_frames = min(30 * sr, total_frames - offset)
        if chunk_frames <= 0:
            chunk_frames = total_frames
            offset = 0

        data, _ = sf.read(
            str(wav_path), start=offset, frames=chunk_frames, dtype="float32"
        )

        if data.size == 0:
            return 0

        # 多声道取均值
        if data.ndim > 1:
            data = data.mean(axis=1)

        rms = float(np.sqrt(np.mean(data ** 2)))

        # RMS → 0-100 映射（基于经验范围）
        score = min(100, max(0, int(rms * 250)))
        return score

    except Exception:
        logger.warning(
            f"[Demucs] RMS 计算失败 {label}: "
            f"{__import__('traceback').format_exc(limit=1)}"
        )
        return 0


def _update_db_scores(
    track_id: int,
    vocal_score: int,
    sub_bass_score: int,
    db_path: str,
) -> None:
    """UPDATE track_audio_features 写入 Demucs 分数。"""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE track_audio_features "
            "SET score_vocal_dominant = ?, score_sub_bass = ?, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE track_id = ?",
            (vocal_score, sub_bass_score, track_id),
        )
        conn.commit()
        conn.close()
        logger.debug(
            f"[Demucs] DB 已更新 track_id={track_id} "
            f"vocal={vocal_score} bass={sub_bass_score}"
        )
    except Exception:
        logger.error(
            f"[Demucs] DB 更新失败 track_id={track_id}: "
            f"{__import__('traceback').format_exc(limit=1)}"
        )


def _cleanup_cache(out_dir: str, track_id: int = 0) -> None:
    """强制删除 Demucs 分离缓存目录，释放磁盘空间。"""
    try:
        if Path(out_dir).exists():
            shutil.rmtree(out_dir, ignore_errors=True)
            logger.debug(f"[Demucs] 已清理缓存: {out_dir}")
    except Exception:
        logger.warning(
            f"[Demucs] 清理缓存失败 track_id={track_id}: "
            f"{__import__('traceback').format_exc(limit=1)}"
        )
