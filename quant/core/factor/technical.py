from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant.core.data.repository import close_price_matrix
from quant.core.factor.base import Factor


@dataclass(frozen=True)
class MomentumFactor(Factor):
    window: int

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"momentum_{self.window}d"

    def calculate(self, bars: pd.DataFrame) -> pd.DataFrame:
        close = close_price_matrix(bars)
        return close.pct_change(self.window).stack().rename(self.name).reset_index()


@dataclass(frozen=True)
class VolatilityFactor(Factor):
    window: int

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"volatility_{self.window}d"

    def calculate(self, bars: pd.DataFrame) -> pd.DataFrame:
        close = close_price_matrix(bars)
        returns = close.pct_change()
        return returns.rolling(self.window).std().stack().rename(self.name).reset_index()


@dataclass(frozen=True)
class MovingAverageFactor(Factor):
    window: int

    @property
    def name(self) -> str:  # type: ignore[override]
        return f"ma_{self.window}d"

    def calculate(self, bars: pd.DataFrame) -> pd.DataFrame:
        close = close_price_matrix(bars)
        return close.rolling(self.window).mean().stack().rename(self.name).reset_index()


class FactorEngine:
    def __init__(self, factors: list[Factor]) -> None:
        self.factors = factors

    def calculate(self, bars: pd.DataFrame) -> pd.DataFrame:
        frames = [factor.calculate(bars) for factor in self.factors]
        if not frames:
            return pd.DataFrame(columns=["trade_date", "ts_code"])

        result = frames[0]
        for frame in frames[1:]:
            result = result.merge(frame, on=["trade_date", "ts_code"], how="outer")
        return result.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
