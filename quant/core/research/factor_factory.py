from __future__ import annotations

from quant.core.factor.base import Factor
from quant.core.factor.quality import QualityScoreFactor
from quant.core.factor.technical import MomentumFactor, MovingAverageFactor, VolatilityFactor


def build_factor(name: str) -> Factor:
    if name.startswith("momentum_") and name.endswith("d"):
        return MomentumFactor(_window_from_name(name, "momentum_"))
    if name.startswith("volatility_") and name.endswith("d"):
        return VolatilityFactor(_window_from_name(name, "volatility_"))
    if name.startswith("ma_") and name.endswith("d"):
        return MovingAverageFactor(_window_from_name(name, "ma_"))
    if name == "quality_score":
        return QualityScoreFactor()
    raise ValueError(f"unsupported factor: {name}")


def _window_from_name(name: str, prefix: str) -> int:
    return int(name.removeprefix(prefix).removesuffix("d"))
