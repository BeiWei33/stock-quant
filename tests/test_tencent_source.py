from __future__ import annotations

import json
from datetime import date

from quant.core.collector.tencent_source import TencentDataSource, TencentDataSourceConfig


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_tencent_source_fetches_and_normalizes_daily_bars() -> None:
    requests: list[str] = []

    def fake_urlopen(request, timeout=0):
        requests.append(request.full_url)
        return FakeResponse(
            {
                "code": 0,
                "data": {
                    "sh600519": {
                        "qt": {"sh600519": ["", "贵州茅台"]},
                        "qfqday": [
                            ["2024-01-02", "10.00", "10.50", "11.00", "9.80", "1000"],
                            ["2024-01-03", "10.50", "10.60", "11.20", "10.20", "1200"],
                        ],
                    }
                },
            }
        )

    source = TencentDataSource(
        TencentDataSourceConfig(symbols=("600519.SH",)),
        urlopen=fake_urlopen,
    )

    result = source.collect(date(2024, 1, 1), date(2024, 1, 31))

    assert result.stocks.iloc[0]["name"] == "贵州茅台"
    assert result.daily_bars["ts_code"].tolist() == ["600519.SH", "600519.SH"]
    assert result.daily_bars.iloc[0]["source"] == "tencent"
    assert result.daily_bars.iloc[0]["adj_type"] == "qfq"
    assert result.daily_bars.iloc[0]["close"] == 10.5
    assert "sh600519,day,2024-01-01,2024-01-31" in requests[0]


def test_tencent_source_can_build_full_market_universe_from_eastmoney_list() -> None:
    requests: list[str] = []

    def fake_urlopen(request, timeout=0):
        requests.append(request.full_url)
        if "clist/get" in request.full_url:
            return FakeResponse(
                {
                    "data": {
                        "diff": [
                            {"f12": "600519", "f14": "贵州茅台"},
                            {"f12": "000001", "f14": "平安银行"},
                        ]
                    }
                }
            )
        symbol = "sh600519" if "sh600519" in request.full_url else "sz000001"
        return FakeResponse(
            {
                "data": {
                    symbol: {
                        "qt": {symbol: ["", "贵州茅台" if symbol == "sh600519" else "平安银行"]},
                        "qfqday": [["2024-01-02", "10", "11", "12", "9", "1000"]],
                    }
                }
            }
        )

    source = TencentDataSource(
        TencentDataSourceConfig(all_market=True, max_symbols=2),
        urlopen=fake_urlopen,
    )

    result = source.collect(date(2024, 1, 1), date(2024, 1, 31))

    assert result.stocks["ts_code"].tolist() == ["600519.SH", "000001.SZ"]
    assert set(result.daily_bars["ts_code"]) == {"600519.SH", "000001.SZ"}
    assert any("clist/get" in url for url in requests)
