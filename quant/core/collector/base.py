from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class CollectionResult:
    stocks: pd.DataFrame
    daily_bars: pd.DataFrame
    benchmark_bars: pd.DataFrame


class MarketDataSource(ABC):
    source_name = "base"

    @abstractmethod
    def fetch_stocks(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def fetch_daily_bars(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        raise NotImplementedError

    def fetch_benchmark_bars(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "benchmark_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "source",
            ]
        )

    def collect(self, start_date: date | None = None, end_date: date | None = None) -> CollectionResult:
        return CollectionResult(
            stocks=self.fetch_stocks(),
            daily_bars=self.fetch_daily_bars(start_date, end_date),
            benchmark_bars=self.fetch_benchmark_bars(start_date, end_date),
        )
