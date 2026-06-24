from __future__ import annotations

from quant.core.strategy.base import Strategy
from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.strategy.quality import QualityRankStrategy
from quant.core.strategy.trend import TrendFilterStrategy


# 脚本策略类型映射到基础策略
SCRIPT_TYPE_MAP = {
    "momentum": "momentum_rank",
    "ma_cross": "momentum_rank",
    "rsi": "momentum_rank",
    "bollinger": "momentum_rank",
    "dual_ma": "momentum_rank_trend",
    "custom": "momentum_rank",
}


def build_strategy(name: str, *, trend_filter: bool = False, **kwargs) -> Strategy:
    # 如果是脚本策略类型，映射到基础策略
    if name in SCRIPT_TYPE_MAP:
        name = SCRIPT_TYPE_MAP[name]

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
