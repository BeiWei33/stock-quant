from __future__ import annotations

import json
import sys
from datetime import date, timedelta

import pandas as pd
import pytest

from quant.core.backtest.multi_strategy import (
    MultiStrategyBacktestEngine,
    MultiStrategyBacktestRequest,
)
from quant.core.capital_allocation import AllocationConfig
from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.strategy.quality import QualityRankStrategy


def _fixtures() -> tuple[pd.DataFrame, pd.DataFrame]:
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(90)]
    dates = [d for d in dates if d.weekday() < 5]
    codes = ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]
    rows = []
    for idx, code in enumerate(codes):
        price = 10.0
        for trade_date in dates:
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
                    "amount": 100_000_000 + idx * 1_000_000,
                    "quality_flag": "NORMAL",
                    "roe": 0.06 + idx * 0.02,
                    "net_profit_growth": 0.08 + idx * 0.03,
                    "debt_to_asset": 0.75 - idx * 0.10,
                }
            )
    stocks = pd.DataFrame(
        {
            "ts_code": codes,
            "name": ["A", "B", "C", "D"],
            "exchange": ["SZ", "SZ", "SZ", "SZ"],
            "industry": ["i1", "i1", "i2", "i2"],
            "list_date": [date(2020, 1, 1)] * 4,
            "is_st": [False] * 4,
            "status": ["listed"] * 4,
        }
    )
    return pd.DataFrame(rows), stocks


def test_multi_strategy_backtest_combines_strategy_returns_with_allocation_weights() -> None:
    bars, stocks = _fixtures()
    result = MultiStrategyBacktestEngine().run(
        MultiStrategyBacktestRequest(
            bars=bars,
            stocks=stocks,
            strategies=[
                MomentumRankStrategy(top_pct=0.5, max_holdings=2),
                QualityRankStrategy(top_pct=0.5, max_holdings=2),
            ],
            allocation_config=AllocationConfig(method="equal"),
            rebalance="weekly",
            initial_cash=1_000_000,
        )
    )

    assert set(result.strategy_results) == {"momentum_rank", "quality_rank"}
    assert set(result.strategy_returns.columns) == {"momentum_rank", "quality_rank"}
    assert result.allocation_records
    assert result.portfolio_returns.index.equals(result.strategy_returns.index)
    assert result.equity_curve.iloc[0] == pytest.approx(1_000_000)
    assert result.equity_curve.iloc[-1] > 1_000_000
    assert "sharpe" in result.metrics
    assert result.metrics["strategy_count"] == 2.0


def test_multi_strategy_backtest_routes_deallocated_weight_to_cash() -> None:
    bars, stocks = _fixtures()
    result = MultiStrategyBacktestEngine().run(
        MultiStrategyBacktestRequest(
            bars=bars,
            stocks=stocks,
            strategies=[
                MomentumRankStrategy(top_pct=0.5, max_holdings=2),
                QualityRankStrategy(top_pct=0.5, max_holdings=2),
            ],
            allocation_config=AllocationConfig(method="equal", target_volatility=0.0001),
            rebalance="weekly",
            initial_cash=1_000_000,
        )
    )

    assert any(
        not record.weights[record.weights["strategy_id"] == "CASH"].empty
        for record in result.allocation_records
    )
    assert result.allocation_history["cash_weight"].max() > 0
    assert result.allocation_history["allocated_weight"].max() <= 1.0


def test_multi_strategy_backtest_initial_allocation_respects_strategy_cap() -> None:
    bars, stocks = _fixtures()
    result = MultiStrategyBacktestEngine().run(
        MultiStrategyBacktestRequest(
            bars=bars,
            stocks=stocks,
            strategies=[
                MomentumRankStrategy(top_pct=0.5, max_holdings=2),
                QualityRankStrategy(top_pct=0.5, max_holdings=2),
            ],
            allocation_config=AllocationConfig(method="equal", max_strategy_weight=0.40),
            rebalance="weekly",
            initial_cash=1_000_000,
        )
    )

    first = result.allocation_records[0]
    assert first.weights["capital_weight"].sum() == pytest.approx(1.0)
    assert first.weights[~first.weights["is_cash"]]["capital_weight"].max() <= 0.40
    assert result.allocation_history.iloc[0]["cash_weight"] == pytest.approx(0.20)


def test_backtest_app_writes_multi_strategy_report(tmp_path, monkeypatch) -> None:
    from quant.apps import backtest

    bars, stocks = _fixtures()
    bars_path = tmp_path / "bars.csv"
    stocks_path = tmp_path / "stocks.csv"
    output_path = tmp_path / "multi_backtest.json"
    output_md_path = tmp_path / "multi_backtest.md"
    bars.to_csv(bars_path, index=False)
    stocks.to_csv(stocks_path, index=False)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backtest",
            "--bars",
            str(bars_path),
            "--stocks",
            str(stocks_path),
            "--multi-strategy",
            "momentum_rank,quality_rank",
            "--allocation-method",
            "equal",
            "--max-strategy-weight",
            "0.40",
            "--output",
            str(output_path),
            "--output-md",
            str(output_md_path),
        ],
    )

    backtest.main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "multi_strategy"
    assert payload["strategies"] == ["momentum_rank", "quality_rank"]
    assert payload["metrics"]["strategy_count"] == 2.0
    assert payload["allocation_history"]
    assert payload["strategy_summary"]
    assert payload["latest_allocation"]
    assert payload["latest_allocation"][-1]["strategy_id"] == "CASH"
    assert "index" not in payload["allocation_history"][0]

    markdown = output_md_path.read_text(encoding="utf-8")
    assert "多策略组合回测报告" in markdown
    assert "策略收益拆解" in markdown
    assert "资金权重变化" in markdown
    assert "现金仓位" in markdown
    assert "momentum_rank" in markdown
    assert "quality_rank" in markdown
