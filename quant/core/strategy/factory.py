from __future__ import annotations

from quant.core.strategy.base import Strategy
from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.strategy.quality import QualityRankStrategy
from quant.core.strategy.trend import TrendFilterStrategy


def build_strategy(name: str, *, trend_filter: bool = False, **kwargs) -> Strategy:
    if name == "momentum_rank":
        strategy: Strategy = MomentumRankStrategy(**kwargs)
    elif name == "quality_rank":
        strategy = QualityRankStrategy(**kwargs)
    elif name == "momentum_rank_trend":
        strategy = TrendFilterStrategy(MomentumRankStrategy(**kwargs))
    elif name == "quality_rank_trend":
        strategy = TrendFilterStrategy(QualityRankStrategy(**kwargs))
    else:
        raise ValueError(f"unsupported strategy: {name}")

    if trend_filter and not isinstance(strategy, TrendFilterStrategy):
        return TrendFilterStrategy(strategy)
    return strategy
