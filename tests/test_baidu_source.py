from __future__ import annotations

import json
from datetime import date

from quant.core.collector.baidu_source import BaiduDataSource, BaiduDataSourceConfig


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_baidu_source_fetches_and_normalizes_daily_bars() -> None:
    requests: list[str] = []

    def fake_urlopen(request, timeout=0):
        requests.append(request.full_url)
        return FakeResponse(
            {
                "Result": {
                    "newMarketData": {
                        "keys": ["date", "open", "close", "high", "low", "volume", "amount"],
                        "marketData": (
                            "2024-01-02,10.00,10.50,11.00,9.80,1000,10000;"
                            "2024-01-03,10.50,10.60,11.20,10.20,1200,12000"
                        ),
                    }
                }
            }
        )

    source = BaiduDataSource(
        BaiduDataSourceConfig(symbols=("600519.SH",)),
        urlopen=fake_urlopen,
    )

    result = source.collect(date(2024, 1, 1), date(2024, 1, 31))

    assert result.daily_bars["ts_code"].tolist() == ["600519.SH", "600519.SH"]
    assert result.daily_bars.iloc[0]["source"] == "baidu"
    assert result.daily_bars.iloc[0]["adj_type"] == "qfq"
    assert result.daily_bars.iloc[0]["close"] == 10.5
    assert "getstockquotation" in requests[0]
    assert "code=600519" in requests[0]


def test_baidu_source_filters_rows_by_requested_date_range() -> None:
    def fake_urlopen(request, timeout=0):
        return FakeResponse(
            {
                "Result": {
                    "newMarketData": {
                        "keys": ["date", "open", "close", "high", "low", "volume"],
                        "marketData": (
                            "2023-12-29,9,9,9,9,100;"
                            "2024-01-02,10,11,12,9,1000"
                        ),
                    }
                }
            }
        )

    source = BaiduDataSource(
        BaiduDataSourceConfig(symbols=("600519.SH",)),
        urlopen=fake_urlopen,
    )

    result = source.collect(date(2024, 1, 1), date(2024, 1, 31))

    assert result.daily_bars["trade_date"].tolist() == [date(2024, 1, 2)]
