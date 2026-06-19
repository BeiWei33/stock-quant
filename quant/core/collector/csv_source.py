from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from quant.core.collector.base import MarketDataSource
from quant.core.collector.normalization import (
    filter_by_date,
    normalize_benchmark_bars,
    normalize_daily_bars,
    normalize_stocks,
)


@dataclass(frozen=True)
class CsvDataSourceConfig:
    stocks_path: Path
    daily_bars_path: Path
    benchmark_bars_path: Path | None = None
    benchmark_code: str = "equal_weight"


class CsvDataSource(MarketDataSource):
    source_name = "csv"

    def __init__(self, config: CsvDataSourceConfig) -> None:
        self.config = config

    def fetch_stocks(self) -> pd.DataFrame:
        return normalize_stocks(pd.read_csv(self.config.stocks_path), self.source_name)

    def fetch_daily_bars(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        bars = normalize_daily_bars(pd.read_csv(self.config.daily_bars_path), self.source_name)
        return filter_by_date(bars, start_date, end_date)

    def fetch_benchmark_bars(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> pd.DataFrame:
        if self.config.benchmark_bars_path is None:
            return super().fetch_benchmark_bars(start_date, end_date)
        bars = normalize_benchmark_bars(
            pd.read_csv(self.config.benchmark_bars_path),
            self.source_name,
            self.config.benchmark_code,
        )
        return filter_by_date(bars, start_date, end_date)
