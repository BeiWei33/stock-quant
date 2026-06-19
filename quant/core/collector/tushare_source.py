from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.collector.base import MarketDataSource
from quant.core.collector.normalization import normalize_daily_bars, normalize_stocks


class TushareDataSource(MarketDataSource):
    source_name = "tushare"

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("tushare token is required")
        try:
            import tushare as ts  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("tushare is not installed. Install it in the trading environment first.") from exc
        ts.set_token(token)
        self.pro = ts.pro_api()

    def fetch_stocks(self) -> pd.DataFrame:
        raw = self.pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,area,industry,list_date",
        )
        raw["exchange"] = raw["ts_code"].str.split(".").str[-1]
        raw["status"] = "listed"
        return normalize_stocks(raw, self.source_name)

    def fetch_daily_bars(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        if start_date is None or end_date is None:
            raise ValueError("tushare daily collection requires start_date and end_date")
        raw = self.pro.daily(
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        return normalize_daily_bars(raw, self.source_name, adj_type="none")
