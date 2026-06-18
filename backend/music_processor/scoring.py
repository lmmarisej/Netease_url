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
