"""6 大物理评分维度 → 0-100 映射函数。"""

from . import config, utils


def score_tempo(tempo_bpm: float) -> int:
    """BPM <80→0-40, 80-120→40-70, >120→70-100。"""
    if tempo_bpm <= 0:
        return 0
    if tempo_bpm < 80:
        return int(round(tempo_bpm / 80.0 * 40))
    elif tempo_bpm <= 120:
        return int(round(40 + (tempo_bpm - 80) / 40.0 * 30))
    else:
        clamped = min(tempo_bpm, 220.0)
        return int(round(70 + (clamped - 120) / 100.0 * 30))


def score_energy(rms_mean: float) -> int:
    return utils.clamp_and_scale(rms_mean,
                                 config.ENERGY_RMS_MIN, config.ENERGY_RMS_MAX)


def score_brightness(centroid_mean: float) -> int:
    return utils.clamp_and_scale(centroid_mean,
                                 config.CENTROID_MIN_HZ, config.CENTROID_MAX_HZ)


def score_rhythm(zcr_mean: float) -> int:
    return utils.clamp_and_scale(zcr_mean,
                                 config.ZCR_MIN, config.ZCR_MAX)


def score_tonality(mfcc_overall_mean: float) -> int:
    return utils.clamp_and_scale(mfcc_overall_mean,
                                 config.MFCC_MEAN_MIN, config.MFCC_MEAN_MAX)


def score_energy_contrast(rms_std: float) -> int:
    return utils.clamp_and_scale(rms_std,
                                 config.ENERGY_STD_MIN, config.ENERGY_STD_MAX)


def score_sub_bass(rolloff_mean: float, centroid_mean: float) -> int:
    """低音轰炸：频谱滚降越低 → 低频能量越多。
    辅助 centroid：越暗越偏重低音。"""
    # rolloff 低 → 能量集中在低频，得分高
    bass_from_rolloff = 100 - utils.clamp_and_scale(
        rolloff_mean, config.ROLLOFF_MIN, config.ROLLOFF_MAX,
    )
    # centroid 低 → 音色偏暗，低音更明显
    bass_from_centroid = 100 - utils.clamp_and_scale(
        centroid_mean, config.CENTROID_MIN_HZ, config.CENTROID_MAX_HZ,
    )
    return int(round(bass_from_rolloff * 0.6 + bass_from_centroid * 0.4))


def score_vocal_dominant(zcr_mean: float, rms_std: float) -> int:
    """人声主导：过零率低 → 波形更平滑（人声特征）；
    动态起伏大 → 更可能有主唱。"""
    vocal_from_zcr = 100 - utils.clamp_and_scale(
        zcr_mean, config.ZCR_MIN, config.ZCR_MAX,
    )
    vocal_from_dynamics = utils.clamp_and_scale(
        rms_std, config.ENERGY_STD_MIN, config.ENERGY_STD_MAX,
    )
    return int(round(vocal_from_zcr * 0.55 + vocal_from_dynamics * 0.45))
