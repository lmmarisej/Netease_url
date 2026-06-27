"""辅助工具函数。"""


def clamp_and_scale(value: float, vmin: float, vmax: float) -> int:
    """将 value 线性映射到 0–100 整数区间，超出 [vmin, vmax] 截断。"""
    if vmax <= vmin:
        return 50
    clamped = max(vmin, min(vmax, value))
    return int(round((clamped - vmin) / (vmax - vmin) * 100.0))
