from __future__ import annotations

from quant.core.strategy.base import Strategy
from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.strategy.quality import QualityRankStrategy
from quant.core.strategy.trend import TrendFilterStrategy


def build_strategy(name: str, *, trend_filter: bool = False) -> Strategy:
    if name == "momentum_rank":
        strategy: Strategy = MomentumRankStrategy()
    elif name == "quality_rank":
        strategy = QualityRankStrategy()
    elif name == "momentum_rank_trend":
        strategy = TrendFilterStrategy(MomentumRankStrategy())
    elif name == "quality_rank_trend":
        strategy = TrendFilterStrategy(QualityRankStrategy())
    else:
        raise ValueError(f"unsupported strategy: {name}")

    if trend_filter and not isinstance(strategy, TrendFilterStrategy):
        return TrendFilterStrategy(strategy)
    return strategy
