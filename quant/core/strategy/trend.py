from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant.core.data.repository import close_price_matrix
from quant.core.factor.base import Factor
from quant.core.strategy.base import Strategy, StrategyContext


@dataclass(frozen=True)
class TrendFilterStrategy(Strategy):
    base_strategy: Strategy
    ma_window: int = 120
    allow_on_insufficient_history: bool = True

    @property
    def strategy_id(self) -> str:  # type: ignore[override]
        return f"{self.base_strategy.strategy_id}_trend"

    @property
    def strategy_version(self) -> str:  # type: ignore[override]
        return self.base_strategy.strategy_version

    def required_factors(self) -> list[Factor]:
        return self.base_strategy.required_factors()

    def generate_signal(self, context: StrategyContext) -> pd.DataFrame:
        if not self._trend_allows_exposure(context):
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
        signals = self.base_strategy.generate_signal(context).copy()
        if not signals.empty:
            signals["strategy_id"] = self.strategy_id
            signals["reason"] = signals["reason"].astype(str) + f"; market_proxy_above_ma{self.ma_window}"
        return signals

    def _trend_allows_exposure(self, context: StrategyContext) -> bool:
        active_codes = set(context.universe.loc[context.universe["is_active"], "ts_code"])
        history = context.bars[
            (context.bars["trade_date"] <= context.trade_date)
            & (context.bars["ts_code"].isin(active_codes))
        ]
        if history.empty:
            return self.allow_on_insufficient_history
        close = close_price_matrix(history)
        proxy = close.mean(axis=1).dropna()
        if len(proxy) < self.ma_window:
            return self.allow_on_insufficient_history
        latest = float(proxy.iloc[-1])
        moving_average = float(proxy.rolling(self.ma_window).mean().iloc[-1])
        return latest > moving_average
