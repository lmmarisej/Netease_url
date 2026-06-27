"""
=============================================================================
  Music Feature Processor — 全局配置与常量
=============================================================================
"""
from pathlib import Path

# ── 路径配置 ──
MUSIC_FOLDER = str((Path(__file__).resolve().parent.parent.parent / "downloads"))
USERNAME = "admin"
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a"}
DB_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "music_vault.db"

# ── librosa 特征提取 ──
LOAD_DURATION_SEC = 60.0

# ── PANNs 标签识别 ──
PANNS_LOAD_DURATION = 10.0
PANNS_SAMPLE_RATE = 32000
PANNS_CONFIDENCE_THRESHOLD = 0.1
PANNS_MAX_TOP_TAGS = 3

# ── 评分归一化边界 ──
ENERGY_RMS_MIN = 0.01
ENERGY_RMS_MAX = 0.30
ENERGY_STD_MIN = 0.005
ENERGY_STD_MAX = 0.08
CENTROID_MIN_HZ = 200.0
CENTROID_MAX_HZ = 5000.0
ZCR_MIN = 0.01
ZCR_MAX = 0.25
MFCC_MEAN_MIN = -80.0
MFCC_MEAN_MAX = 30.0
ROLLOFF_MIN = 500.0
ROLLOFF_MAX = 12000.0
