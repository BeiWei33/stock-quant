from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.collector.mootdx_source import MootdxDataSource, MootdxDataSourceConfig


class FakeClient:
    def bars(self, symbol, category, offset):
        assert symbol == "600519"
        assert category == 4
        assert offset == 800
        return pd.DataFrame(
            [
                {
                    "datetime": "2024-01-02",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.8,
                    "close": 10.5,
                    "vol": 1000,
                    "amount": 10000,
                },
                {
                    "datetime": "2024-01-03",
                    "open": 10.5,
                    "high": 11.2,
                    "low": 10.2,
                    "close": 10.6,
                    "vol": 1200,
                    "amount": 12000,
                },
            ]
        )


def test_mootdx_source_fetches_and_normalizes_daily_bars() -> None:
    source = MootdxDataSource(
        MootdxDataSourceConfig(symbols=("600519.SH",), max_bars_per_symbol=800),
        client_factory=lambda: FakeClient(),
    )

    result = source.collect(date(2024, 1, 1), date(2024, 1, 31))

    assert result.daily_bars["ts_code"].tolist() == ["600519.SH", "600519.SH"]
    assert result.daily_bars.iloc[0]["source"] == "mootdx"
    assert result.daily_bars.iloc[0]["adj_type"] == "qfq"
    assert result.daily_bars.iloc[0]["close"] == 10.5


def test_mootdx_source_defers_import_until_used() -> None:
    source = MootdxDataSource(MootdxDataSourceConfig(symbols=("600519.SH",)), client_factory=lambda: FakeClient())

    assert source.source_name == "mootdx"
