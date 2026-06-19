from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant.core.factor.base import Factor
from quant.core.factor.quality import QualityScoreFactor
from quant.core.strategy.base import Strategy, StrategyContext


@dataclass(frozen=True)
class QualityRankStrategy(Strategy):
    strategy_id: str = "quality_rank"
    strategy_version: str = "v1"
    factor_name: str = "quality_score"
    top_pct: float = 0.10
    max_holdings: int = 20
    min_score: float = 0.0

    def required_factors(self) -> list[Factor]:
        return [QualityScoreFactor()]

    def generate_signal(self, context: StrategyContext) -> pd.DataFrame:
        active_codes = set(context.universe.loc[context.universe["is_active"], "ts_code"])
        today_factor = context.factors[
            (context.factors["trade_date"] == context.trade_date)
            & (context.factors["ts_code"].isin(active_codes))
        ][["ts_code", self.factor_name]].dropna()
        today_factor = today_factor[today_factor[self.factor_name] >= self.min_score]

        if today_factor.empty:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "ts_code",
                    "strategy_id",
                    "strategy_version",
                    "signal_type",
                    "score",
                    "reason",
                ]
            )

        top_n = min(self.max_holdings, max(1, int(len(today_factor) * self.top_pct)))
        selected = today_factor.nlargest(top_n, self.factor_name).copy()
        selected["trade_date"] = context.trade_date
        selected["strategy_id"] = self.strategy_id
        selected["strategy_version"] = self.strategy_version
        selected["signal_type"] = "BUY"
        selected["score"] = selected[self.factor_name]
        selected["reason"] = f"top {top_n} by {self.factor_name}"
        return selected[
            [
                "trade_date",
                "ts_code",
                "strategy_id",
                "strategy_version",
                "signal_type",
                "score",
                "reason",
            ]
        ].reset_index(drop=True)
