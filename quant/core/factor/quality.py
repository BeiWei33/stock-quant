from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant.core.data.repository import amount_matrix, close_price_matrix
from quant.core.factor.base import Factor


@dataclass(frozen=True)
class QualityScoreFactor(Factor):
    """Cross-sectional quality score from fundamentals, with a market-data fallback."""

    window: int = 60
    name: str = "quality_score"

    def calculate(self, bars: pd.DataFrame) -> pd.DataFrame:
        df = bars.copy()
        fundamental = _fundamental_quality_score(df)
        if fundamental is not None:
            return fundamental
        return self._market_quality_proxy(df)

    def _market_quality_proxy(self, bars: pd.DataFrame) -> pd.DataFrame:
        close = close_price_matrix(bars)
        amount = amount_matrix(bars)
        volatility = close.pct_change().rolling(self.window).std()
        liquidity = amount.rolling(self.window).mean()
        liquidity_rank = liquidity.rank(axis=1, pct=True)
        low_vol_rank = 1.0 - volatility.rank(axis=1, pct=True)
        score = ((liquidity_rank + low_vol_rank) / 2.0).stack().rename(self.name).reset_index()
        return score.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)


def _fundamental_quality_score(bars: pd.DataFrame) -> pd.DataFrame | None:
    positive_columns = [column for column in ["roe", "roa", "net_profit_growth"] if column in bars.columns]
    negative_columns = [column for column in ["debt_to_asset"] if column in bars.columns]
    if not positive_columns and not negative_columns:
        return None

    df = bars[["trade_date", "ts_code", *positive_columns, *negative_columns]].copy()
    score = pd.Series(0.0, index=df.index)
    component_count = 0
    for column in positive_columns:
        values = pd.to_numeric(df[column], errors="coerce")
        score += values.groupby(df["trade_date"]).rank(pct=True)
        component_count += 1
    for column in negative_columns:
        values = pd.to_numeric(df[column], errors="coerce")
        score += 1.0 - values.groupby(df["trade_date"]).rank(pct=True)
        component_count += 1
    df["quality_score"] = score / component_count if component_count else pd.NA
    return (
        df[["trade_date", "ts_code", "quality_score"]]
        .dropna()
        .sort_values(["trade_date", "ts_code"])
        .reset_index(drop=True)
    )
