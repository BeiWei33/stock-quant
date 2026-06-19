from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant.core.factor.base import Factor


@dataclass(frozen=True)
class StrategyContext:
    trade_date: date
    universe: pd.DataFrame
    bars: pd.DataFrame
    factors: pd.DataFrame


class Strategy(ABC):
    strategy_id = ""
    strategy_version = "v1"

    def required_factors(self) -> list[Factor]:
        return []

    @abstractmethod
    def generate_signal(self, context: StrategyContext) -> pd.DataFrame:
        raise NotImplementedError
