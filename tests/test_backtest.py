from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from quant.core.backtest.engine import BacktestEngine, BacktestRequest
from quant.core.benchmark.returns import benchmark_returns
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.strategy.momentum import MomentumRankStrategy


def _fixtures() -> tuple[pd.DataFrame, pd.DataFrame]:
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(90)]
    dates = [d for d in dates if d.weekday() < 5]
    codes = ["000001.SZ", "000002.SZ", "000003.SZ"]
    rows = []
    for idx, code in enumerate(codes):
        price = 10.0
        for step, trade_date in enumerate(dates):
            price *= 1.0 + 0.001 * (idx + 1)
            rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date,
                    "adj_type": "qfq",
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1_000_000,
                    "amount": 100_000_000,
                    "quality_flag": "NORMAL",
                }
            )
    stocks = pd.DataFrame(
        {
            "ts_code": codes,
            "name": ["A", "B", "C"],
            "exchange": ["SZ", "SZ", "SZ"],
            "industry": ["i1", "i2", "i3"],
            "list_date": [date(2020, 1, 1)] * 3,
            "is_st": [False] * 3,
            "status": ["listed"] * 3,
        }
    )
    return pd.DataFrame(rows), stocks


def test_backtest_runs_and_emits_snapshots() -> None:
    bars, stocks = _fixtures()
    engine = BacktestEngine()
    result = engine.run(
        BacktestRequest(
            bars=bars,
            stocks=stocks,
            strategy=MomentumRankStrategy(top_pct=0.5, max_holdings=2),
            rebalance="weekly",
        )
    )

    assert result.snapshots
    assert result.rebalance_records
    assert "total_return" in result.metrics
    assert "benchmark_total_return" in result.metrics
    assert "tracking_error" in result.metrics
    assert "active_win_rate" in result.metrics
    assert "rebalance_count" in result.metrics
    assert "average_turnover" in result.metrics
    assert "filled_order_count" in result.metrics
    assert "rejected_order_count" in result.metrics
    assert "information_ratio" in result.metrics
    assert result.strategy_registration.strategy_id == "momentum_rank"
    assert result.strategy_registration.config_hash
    assert result.rebalance_records[-1].turnover >= 0
    assert result.rebalance_records[-1].holdings_count >= 0
    assert isinstance(result.rebalance_records[-1].target_weights, list)
    assert len(result.benchmark_returns) == len(result.returns)
    assert len(result.active_returns) == len(result.returns)
    assert result.equity_curve.iloc[-1] == result.snapshots[-1].total_asset
    assert result.benchmark_equity_curve.iloc[-1] > 0
    assert result.snapshots[-1].total_asset > 0


def test_backtest_can_use_market_data_loaded_from_sqlite(tmp_path) -> None:
    bars, stocks = _fixtures()
    store = SqliteStore(tmp_path / "market.sqlite3")
    store.init_schema()
    stocks = stocks.assign(source="test", delist_date=None)
    bars = bars.assign(source="test")
    store.save_stocks(stocks)
    store.save_daily_bars(bars)

    engine = BacktestEngine()
    result = engine.run(
        BacktestRequest(
            bars=store.load_daily_bars(adj_type="qfq"),
            stocks=store.load_stocks(),
            strategy=MomentumRankStrategy(top_pct=0.5, max_holdings=2),
            rebalance="weekly",
        )
    )

    assert result.snapshots


def test_backtest_uses_external_benchmark_bars() -> None:
    bars, stocks = _fixtures()
    dates = sorted(bars["trade_date"].unique())
    benchmark_bars = pd.DataFrame(
        [
            {
                "benchmark_code": "hs300",
                "trade_date": trade_date,
                "open": 100.0 + idx,
                "high": 100.0 + idx,
                "low": 100.0 + idx,
                "close": 100.0 * (1.001 ** idx),
                "volume": 1_000_000,
                "source": "test",
            }
            for idx, trade_date in enumerate(dates)
        ]
    )

    result = BacktestEngine().run(
        BacktestRequest(
            bars=bars,
            stocks=stocks,
            strategy=MomentumRankStrategy(top_pct=0.5, max_holdings=2),
            benchmark_bars=benchmark_bars,
            benchmark_code="hs300",
            rebalance="weekly",
        )
    )

    expected = benchmark_returns(
        bars=bars,
        benchmark_bars=benchmark_bars,
        benchmark_code="hs300",
    ).reindex(result.returns.index).fillna(0.0)
    assert result.benchmark_code == "hs300"
    assert result.metrics["benchmark_code"] == "hs300"
    assert result.benchmark_returns.equals(expected)


def test_external_benchmark_requires_matching_code() -> None:
    bars, _ = _fixtures()
    benchmark_bars = pd.DataFrame(
        [{"benchmark_code": "zz500", "trade_date": date(2024, 1, 1), "close": 100.0}]
    )

    with pytest.raises(ValueError, match="benchmark code not found"):
        benchmark_returns(bars=bars, benchmark_bars=benchmark_bars, benchmark_code="hs300")


def test_backtest_rejects_limit_up_buy_orders() -> None:
    bars, stocks = _fixtures()
    bars = bars.copy()
    bars.loc[bars["ts_code"] == "000003.SZ", "quality_flag"] = "LIMIT_UP"

    result = BacktestEngine().run(
        BacktestRequest(
            bars=bars,
            stocks=stocks,
            strategy=MomentumRankStrategy(top_pct=1.0, max_holdings=3),
            rebalance="weekly",
        )
    )

    assert result.metrics["rejected_order_count"] > 0
    assert any(record.rejected_orders for record in result.rebalance_records)
