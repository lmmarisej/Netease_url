"""librosa 声学特征提取。"""

import traceback

import numpy as np

from . import config


def extract_features(file_path: str) -> dict | None:
    """提取 tempo / RMS mean+std / centroid / rolloff / ZCR / MFCC。"""
    try:
        import librosa
    except ImportError:
        print("[错误] 未安装 librosa，请先执行: pip install librosa soundfile")
        return None

    try:
        y, sr = librosa.load(file_path, sr=None, mono=True,
                             duration=config.LOAD_DURATION_SEC)
        if len(y) == 0:
            print(f"  [警告] 音频数据为空: {file_path}")
            return None

        tempo_arr, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.asarray(tempo_arr).flat[0]) if tempo_arr is not None else 0.0

        rms      = librosa.feature.rms(y=y)
        rms_mean = float(np.mean(rms))
        rms_std  = float(np.std(rms))

        centroid       = librosa.feature.spectral_centroid(y=y, sr=sr)
        centroid_mean  = float(np.mean(centroid))

        rolloff       = librosa.feature.spectral_rolloff(y=y, sr=sr)
        rolloff_mean  = float(np.mean(rolloff))

        zcr      = librosa.feature.zero_crossing_rate(y)
        zcr_mean = float(np.mean(zcr))

        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_overall_mean = float(np.mean(np.mean(mfcc, axis=1)))

        return {
            "tempo": round(tempo, 2),
            "rms_mean": round(rms_mean, 6),
            "rms_std": round(rms_std, 6),
            "centroid_mean": round(centroid_mean, 2),
            "rolloff_mean": round(rolloff_mean, 2),
            "zcr_mean": round(zcr_mean, 6),
            "mfcc_mean": round(mfcc_overall_mean, 2),
        }
    except Exception:
        print(f"  [错误] 音频特征提取失败: {file_path}")
        traceback.print_exc()
        return None
