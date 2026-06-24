from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant.core.factor.base import Factor
from quant.core.factor.technical import MomentumFactor
from quant.core.strategy.base import Strategy, StrategyContext


@dataclass(frozen=True)
class MomentumRankStrategy(Strategy):
    strategy_id: str = "momentum_rank"
    strategy_version: str = "v1"
    factor_name: str = "momentum_60d"
    max_holdings: int = 20

    def required_factors(self) -> list[Factor]:
        if self.factor_name.startswith("momentum_") and self.factor_name.endswith("d"):
            window = int(self.factor_name.removeprefix("momentum_").removesuffix("d"))
            return [MomentumFactor(window)]
        return []

    def generate_signal(self, context: StrategyContext) -> pd.DataFrame:
        active_codes = set(context.universe.loc[context.universe["is_active"], "ts_code"])
        today_factor = context.factors[
            (context.factors["trade_date"] == context.trade_date)
            & (context.factors["ts_code"].isin(active_codes))
        ][["ts_code", self.factor_name]].dropna()

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

        # 直接按 max_holdings 选股
        top_n = min(self.max_holdings, len(today_factor))
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
