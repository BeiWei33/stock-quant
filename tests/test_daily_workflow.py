from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from quant.core.collector.csv_source import CsvDataSource, CsvDataSourceConfig
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.workflow.daily import DailyWorkflow, DailyWorkflowConfig


def _write_source_files(tmp_path):
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(180)]
    dates = [d for d in dates if d.weekday() < 5]
    codes = [f"0000{i:02d}.SZ" for i in range(1, 31)]
    stocks = pd.DataFrame(
        {
            "ts_code": codes,
            "name": [f"S{i}" for i in range(len(codes))],
            "exchange": ["SZ"] * len(codes),
            "industry": [f"industry_{i % 5}" for i in range(len(codes))],
            "list_date": [date(2020, 1, 1)] * len(codes),
            "is_st": [False] * len(codes),
            "status": ["listed"] * len(codes),
        }
    )
    rows = []
    for idx, code in enumerate(codes):
        price = 10.0
        for trade_date in dates:
            price *= 1.0 + 0.0005 * (idx + 1)
            rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date,
                    "adj_type": "qfq",
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "pre_close": price,
                    "volume": 1_000_000,
                    "amount": 100_000_000,
                    "quality_flag": "NORMAL",
                }
            )

    stocks_path = tmp_path / "stocks.csv"
    bars_path = tmp_path / "daily_bar.csv"
    stocks.to_csv(stocks_path, index=False)
    pd.DataFrame(rows).to_csv(bars_path, index=False)
    return stocks_path, bars_path


def test_daily_workflow_runs_collection_research_trading_and_state(tmp_path) -> None:
    stocks_path, bars_path = _write_source_files(tmp_path)
    workflow = DailyWorkflow(
        DailyWorkflowConfig(
            market_store_path=tmp_path / "market.sqlite3",
            paper_store_path=tmp_path / "paper.sqlite3",
            report_dir=tmp_path / "reports",
            initial_cash=1_000_000,
        )
    )

    result = workflow.run(
        source=CsvDataSource(
            CsvDataSourceConfig(stocks_path=stocks_path, daily_bars_path=bars_path)
        )
    )

    assert result.ok
    assert result.collected_stocks == 30
    assert result.collected_daily_bars > 0
    assert result.fill_count > 0
    assert result.snapshot is not None
    assert result.data_quality_level == "INFO"
    assert (tmp_path / "reports" / "data_quality.md").exists()
    assert (tmp_path / "reports" / "alpha" / "momentum_60d_h5.md").exists()

    paper_store = SqliteStore(tmp_path / "paper.sqlite3")
    assert paper_store.count_rows("order_fill") == result.fill_count
    assert paper_store.count_rows("portfolio_snapshot") == 1


def test_daily_workflow_quality_gate_can_block_research_and_trading(tmp_path) -> None:
    stocks_path, bars_path = _write_source_files(tmp_path)
    bars = pd.read_csv(bars_path)
    bars.loc[0, "high"] = bars.loc[0, "low"] - 1
    bars.to_csv(bars_path, index=False)
    workflow = DailyWorkflow(
        DailyWorkflowConfig(
            market_store_path=tmp_path / "market.sqlite3",
            paper_store_path=tmp_path / "paper.sqlite3",
            report_dir=tmp_path / "reports",
            initial_cash=1_000_000,
            fail_on_quality_error=True,
        )
    )

    with pytest.raises(ValueError, match="data quality gate failed"):
        workflow.run(
            source=CsvDataSource(
                CsvDataSourceConfig(stocks_path=stocks_path, daily_bars_path=bars_path)
            )
        )

    assert (tmp_path / "reports" / "data_quality.json").exists()
    assert not (tmp_path / "reports" / "alpha" / "momentum_60d_h5.md").exists()
