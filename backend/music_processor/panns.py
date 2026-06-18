"""PANNs (CNN14) 深度学习音频标签识别。"""

import traceback

from . import config

_panns_model: object | None = None


def init_panns() -> object | None:
    """延迟加载 PANNs CNN14 模型（CPU 推理），需预先下载 labels CSV + 权重。"""
    global _panns_model
    if _panns_model is not None:
        return _panns_model
    try:
        from panns_inference import AudioTagging
    except Exception:
        print("[提示] 未安装 panns-inference，跳过 AI 标签识别")
        return None
    try:
        _panns_model = AudioTagging(checkpoint_path=None, device="cpu")
        print("[PANNs] CNN14 模型加载完成 (device=cpu)")
        return _panns_model
    except Exception:
        print("[警告] PANNs 模型加载失败，跳过 AI 标签识别")
        traceback.print_exc()
        return None


def extract_panns_tags(file_path: str) -> list[dict]:
    """PANNs 推理 → 筛选 >10% 标签 → [{tag_name, confidence}, ...] 降序。"""
    at = init_panns()
    if at is None:
        return []
    try:
        import librosa
    except ImportError:
        return []
    try:
        y, _ = librosa.load(file_path, sr=config.PANNS_SAMPLE_RATE,
                            mono=True, duration=config.PANNS_LOAD_DURATION)
        if len(y) == 0:
            return []
        if y.ndim == 1:
            y = y[None, :]
        clipwise_output, _ = at.inference(y)
        scores = clipwise_output[0]
        result = []
        for i, s in enumerate(scores):
            score_val = float(s)
            if score_val > config.PANNS_CONFIDENCE_THRESHOLD:
                result.append({
                    "tag_name": at.labels[i],
                    "confidence": int(round(score_val * 100)),
                })
        result.sort(key=lambda x: x["confidence"], reverse=True)
        return result
    except Exception:
        print(f"  [PANNs] 标签识别跳过: {file_path}")
        traceback.print_exc()
        return []
