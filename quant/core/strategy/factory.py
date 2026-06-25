from __future__ import annotations

from quant.core.strategy.base import Strategy
from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.strategy.quality import QualityRankStrategy
from quant.core.strategy.trend import TrendFilterStrategy


def build_strategy(name: str, *, trend_filter: bool = False, **kwargs) -> Strategy:
    """构建策略实例。

    Args:
        name: 策略名称或类型
        trend_filter: 是否添加趋势过滤
        **kwargs: 策略参数

    Returns:
        Strategy 实例
    """
    # 处理自定义脚本策略
    if name in ("custom", "custom_script"):
        script_code = kwargs.pop("script_code", None)
        if script_code:
            from quant.core.strategy.script_adapter import ScriptStrategyAdapter
            strategy = ScriptStrategyAdapter(script_code, strategy_id="custom_script")
            return strategy
        # 如果没有脚本代码，回退到 momentum_rank
        name = "momentum_rank"

    # 处理脚本类型映射
    script_type_map = {
        "momentum": "momentum_rank",
        "ma_cross": "momentum_rank",
        "rsi": "momentum_rank",
        "bollinger": "momentum_rank",
        "dual_ma": "momentum_rank_trend",
    }
    if name in script_type_map:
        name = script_type_map[name]

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
