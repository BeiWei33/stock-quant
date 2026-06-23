from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.collector.akshare_source import AkShareDataSource, AkShareDataSourceConfig
from quant.core.collector.csv_source import CsvDataSource, CsvDataSourceConfig
from quant.core.data.repository import CsvDailyBarRepository
from quant.core.persistence.sqlite_store import SqliteStore


def test_csv_collector_normalizes_and_filters_dates(tmp_path) -> None:
    stocks_path = tmp_path / "stocks.csv"
    bars_path = tmp_path / "bars.csv"
    pd.DataFrame(
        [
            {
                "ts_code": "1",
                "name": "A",
                "exchange": "SZ",
                "industry": "bank",
                "list_date": "2020-01-01",
                "is_st": False,
                "status": "listed",
            }
        ]
    ).to_csv(stocks_path, index=False)
    pd.DataFrame(
        [
            {
                "ts_code": "1",
                "trade_date": "2024-01-02",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10,
                "volume": 100,
                "amount": 1000,
            },
            {
                "ts_code": "1",
                "trade_date": "2024-01-03",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10,
                "volume": 0,
                "amount": 0,
            },
        ]
    ).to_csv(bars_path, index=False)

    source = CsvDataSource(CsvDataSourceConfig(stocks_path=stocks_path, daily_bars_path=bars_path))
    result = source.collect(start_date=date(2024, 1, 3), end_date=date(2024, 1, 3))

    assert result.stocks.iloc[0]["ts_code"] == "000001.SZ"
    assert len(result.daily_bars) == 1
    assert result.daily_bars.iloc[0]["quality_flag"] == "ZERO_VOLUME"


def test_akshare_collector_uses_configured_symbols_and_normalizes_bars() -> None:
    class FakeAk:
        def stock_info_a_code_name(self):
            return pd.DataFrame(
                [
                    {"code": "600519", "name": "贵州茅台"},
                    {"code": "000001", "name": "平安银行"},
                    {"code": "300750", "name": "宁德时代"},
                ]
            )

        def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
            return pd.DataFrame(
                [
                    {
                        "日期": "2024-01-02",
                        "开盘": 10,
                        "最高": 11,
                        "最低": 9,
                        "收盘": 10.5,
                        "成交量": 1000,
                        "成交额": 10500,
                    }
                ]
            )

    source = AkShareDataSource(
        AkShareDataSourceConfig(symbols=("600519.SH", "000001.SZ"), max_symbols=1),
        ak_module=FakeAk(),
    )

    result = source.collect(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    assert result.stocks["ts_code"].tolist() == ["600519.SH"]
    assert result.stocks.iloc[0]["name"] == "贵州茅台"
    assert result.daily_bars.iloc[0]["ts_code"] == "600519.SH"
    assert result.daily_bars.iloc[0]["source"] == "akshare"
    assert result.daily_bars.iloc[0]["adj_type"] == "qfq"


def test_akshare_collector_can_use_full_market_without_symbol_filter() -> None:
    class FakeAk:
        def stock_info_a_code_name(self):
            return pd.DataFrame(
                [
                    {"code": "600519", "name": "贵州茅台"},
                    {"code": "000001", "name": "平安银行"},
                    {"code": "300750", "name": "宁德时代"},
                ]
            )

        def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
            return pd.DataFrame(
                [
                    {
                        "日期": "2024-01-02",
                        "开盘": 10,
                        "最高": 11,
                        "最低": 9,
                        "收盘": 10.5,
                        "成交量": 1000,
                        "成交额": 10500,
                    }
                ]
            )

    source = AkShareDataSource(
        AkShareDataSourceConfig(symbols=("600519.SH",), all_market=True),
        ak_module=FakeAk(),
    )

    result = source.collect(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    assert result.stocks["ts_code"].tolist() == ["600519.SH", "000001.SZ", "300750.SZ"]
    assert set(result.daily_bars["ts_code"]) == {"600519.SH", "000001.SZ", "300750.SZ"}


def test_akshare_collector_retries_and_chunks_long_ranges() -> None:
    class FlakyAk:
        def __init__(self):
            self.calls: list[tuple[str, str, str]] = []

        def stock_info_a_code_name(self):
            return pd.DataFrame([{"code": "000001", "name": "平安银行"}])

        def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
            self.calls.append((symbol, start_date, end_date))
            if len(self.calls) == 1:
                raise ConnectionError("temporary disconnect")
            return pd.DataFrame(
                [
                    {
                        "日期": start_date,
                        "开盘": 10,
                        "最高": 11,
                        "最低": 9,
                        "收盘": 10.5,
                        "成交量": 1000,
                        "成交额": 10500,
                    }
                ]
            )

    fake = FlakyAk()
    source = AkShareDataSource(
        AkShareDataSourceConfig(
            symbols=("000001.SZ",),
            retry_count=2,
            retry_sleep_seconds=0,
            chunk_days=31,
        ),
        ak_module=fake,
    )

    result = source.collect(start_date=date(2024, 1, 1), end_date=date(2024, 3, 15))

    assert len(fake.calls) == 4
    assert result.daily_bars["trade_date"].tolist() == [
        date(2024, 1, 1),
        date(2024, 2, 1),
        date(2024, 3, 3),
    ]


def test_akshare_full_market_limit_counts_successful_symbols() -> None:
    class FakeAk:
        def stock_info_a_code_name(self):
            return pd.DataFrame(
                [
                    {"code": "000001", "name": "平安银行"},
                    {"code": "600519", "name": "贵州茅台"},
                ]
            )

        def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
            if symbol == "000001":
                raise ConnectionError("remote disconnected")
            return pd.DataFrame(
                [
                    {
                        "日期": "2024-01-02",
                        "开盘": 10,
                        "最高": 11,
                        "最低": 9,
                        "收盘": 10.5,
                        "成交量": 1000,
                        "成交额": 10500,
                    }
                ]
            )

    source = AkShareDataSource(
        AkShareDataSourceConfig(
            all_market=True,
            max_symbols=1,
            retry_count=1,
            retry_sleep_seconds=0,
        ),
        ak_module=FakeAk(),
    )

    result = source.collect(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    assert result.stocks["ts_code"].tolist() == ["600519.SH"]
    assert result.daily_bars["ts_code"].tolist() == ["600519.SH"]


def test_akshare_full_market_prioritizes_stable_default_symbols() -> None:
    class FakeAk:
        def __init__(self):
            self.symbols: list[str] = []

        def stock_info_a_code_name(self):
            return pd.DataFrame(
                [
                    {"code": "000001", "name": "平安银行"},
                    {"code": "600519", "name": "贵州茅台"},
                ]
            )

        def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
            self.symbols.append(symbol)
            return pd.DataFrame(
                [
                    {
                        "日期": "2024-01-02",
                        "开盘": 10,
                        "最高": 11,
                        "最低": 9,
                        "收盘": 10.5,
                        "成交量": 1000,
                        "成交额": 10500,
                    }
                ]
            )

    fake = FakeAk()
    source = AkShareDataSource(
        AkShareDataSourceConfig(all_market=True, max_symbols=1),
        ak_module=fake,
    )

    result = source.collect(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    assert fake.symbols == ["600519"]
    assert result.stocks["ts_code"].tolist() == ["600519.SH"]
    assert result.daily_bars["ts_code"].tolist() == ["600519.SH"]


def test_akshare_collector_falls_back_to_daily_endpoint() -> None:
    class FakeAk:
        def __init__(self):
            self.fallback_symbols: list[str] = []

        def stock_info_a_code_name(self):
            return pd.DataFrame([{"code": "600519", "name": "贵州茅台"}])

        def stock_zh_a_hist(self, symbol, period, start_date, end_date, adjust):
            raise ConnectionError("primary disconnected")

        def stock_zh_a_daily(self, symbol, start_date, end_date, adjust):
            self.fallback_symbols.append(symbol)
            return pd.DataFrame(
                [
                    {
                        "date": "2024-01-02",
                        "open": 10,
                        "high": 11,
                        "low": 9,
                        "close": 10.5,
                        "volume": 1000,
                        "amount": 10500,
                    }
                ]
            )

    fake = FakeAk()
    source = AkShareDataSource(
        AkShareDataSourceConfig(symbols=("600519.SH",), retry_count=1),
        ak_module=fake,
    )

    result = source.collect(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    assert fake.fallback_symbols == ["sh600519"]
    assert result.daily_bars.iloc[0]["ts_code"] == "600519.SH"
    assert result.daily_bars.iloc[0]["trade_date"] == date(2024, 1, 2)


def test_sqlite_store_persists_and_loads_market_data(tmp_path) -> None:
    store = SqliteStore(tmp_path / "market.sqlite3")
    store.init_schema()
    stocks = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "name": "A",
                "exchange": "SZ",
                "industry": "bank",
                "list_date": date(2020, 1, 1),
                "delist_date": None,
                "is_st": False,
                "status": "listed",
                "source": "test",
            }
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 2),
                "adj_type": "qfq",
                "open": 10.0,
                "high": 10.5,
                "low": 9.9,
                "close": 10.2,
                "pre_close": 10.0,
                "volume": 1000,
                "amount": 10000.0,
                "source": "test",
                "quality_flag": "NORMAL",
            }
        ]
    )

    store.save_stocks(stocks)
    store.save_daily_bars(bars)

    assert store.count_rows("stocks") == 1
    assert store.count_rows("daily_bar") == 1
    assert store.load_stocks().iloc[0]["ts_code"] == "000001.SZ"
    assert store.load_daily_bars(adj_type="qfq").iloc[0]["trade_date"] == date(2024, 1, 2)


def test_csv_daily_bar_repository_defaults_optional_columns(tmp_path) -> None:
    bars_path = tmp_path / "bars.csv"
    pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "2024-01-02",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10,
                "volume": 100,
                "amount": 1000,
            }
        ]
    ).to_csv(bars_path, index=False)

    bars = CsvDailyBarRepository(bars_path).load()

    assert bars.iloc[0]["quality_flag"] == "NORMAL"
    assert bars.iloc[0]["adj_type"] == "none"
