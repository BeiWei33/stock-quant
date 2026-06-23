from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant.core.collector.base import CollectionResult, MarketDataSource
from quant.core.collector.fallback_source import FallbackMarketDataSource


class StubSource(MarketDataSource):
    def __init__(
        self,
        name: str,
        *,
        daily_bars: pd.DataFrame | None = None,
        error: Exception | None = None,
    ) -> None:
        self.source_name = name
        self._daily_bars = daily_bars
        self._error = error

    def fetch_stocks(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ts_code": "600519.SH",
                    "name": "贵州茅台",
                    "exchange": "SH",
                    "industry": "UNKNOWN",
                    "list_date": pd.NaT,
                    "delist_date": pd.NaT,
                    "is_st": False,
                    "status": "listed",
                    "source": self.source_name,
                }
            ]
        )

    def fetch_daily_bars(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        if self._error is not None:
            raise self._error
        assert self._daily_bars is not None
        return self._daily_bars

    def collect(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> CollectionResult:
        return CollectionResult(
            stocks=self.fetch_stocks(),
            daily_bars=self.fetch_daily_bars(start_date, end_date),
            benchmark_bars=pd.DataFrame(),
        )


def _bars(source: str = "tencent") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": date(2024, 1, 2),
                "adj_type": "qfq",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "pre_close": pd.NA,
                "volume": 1000,
                "amount": 10000,
                "source": source,
                "quality_flag": "NORMAL",
            }
        ]
    )


def test_fallback_source_tries_next_source_after_error() -> None:
    source = FallbackMarketDataSource(
        [
            StubSource("mootdx", error=RuntimeError("tcp unavailable")),
            StubSource("tencent", daily_bars=_bars()),
        ]
    )

    result = source.collect(date(2024, 1, 1), date(2024, 1, 31))

    assert result.daily_bars.iloc[0]["source"] == "tencent"
    assert [(item.source_name, item.status) for item in source.attempts] == [
        ("mootdx", "FAIL"),
        ("tencent", "OK"),
    ]


def test_fallback_source_treats_empty_daily_bars_as_unavailable() -> None:
    source = FallbackMarketDataSource(
        [
            StubSource("tencent", daily_bars=pd.DataFrame()),
            StubSource("akshare", daily_bars=_bars("akshare")),
        ]
    )

    result = source.collect(date(2024, 1, 1), date(2024, 1, 31))

    assert result.daily_bars.iloc[0]["source"] == "akshare"
    assert source.attempts[0].error == "source returned no daily bars"


def test_fallback_source_reports_all_failed_sources() -> None:
    source = FallbackMarketDataSource(
        [
            StubSource("tencent", error=RuntimeError("http 403")),
            StubSource("akshare", error=RuntimeError("remote disconnected")),
        ]
    )

    with pytest.raises(RuntimeError, match="tencent: http 403.*akshare: remote disconnected"):
        source.collect(date(2024, 1, 1), date(2024, 1, 31))
