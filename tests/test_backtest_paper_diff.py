from __future__ import annotations

import json
from datetime import date

import pandas as pd

from quant.core.models import PortfolioSnapshot
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.reconciliation.backtest_paper import (
    compare_backtest_to_paper,
    render_diff_markdown,
    write_diff_json,
    write_diff_markdown,
)


def test_compare_backtest_to_paper_reports_weight_diff(tmp_path) -> None:
    backtest_path = tmp_path / "backtest.json"
    backtest_path.write_text(
        json.dumps(
            {
                "rebalance_records": [
                    {
                        "trade_date": "2024-01-31",
                        "target_weights": [
                            {"ts_code": "000001.SZ", "target_weight": 0.10},
                            {"ts_code": "000002.SZ", "target_weight": 0.10},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    trade_date = date(2024, 1, 31)
    store.save_positions(
        pd.DataFrame(
            [
                {
                    "account_id": "paper",
                    "ts_code": "000001.SZ",
                    "trade_date": trade_date,
                    "quantity": 100,
                    "available_quantity": 100,
                    "avg_cost": 10.0,
                    "market_value": 1000.0,
                    "weight": 1.0,
                }
            ]
        )
    )
    store.save_portfolio_snapshots(
        [
            PortfolioSnapshot(
                account_id="paper",
                trade_date=trade_date,
                total_asset=10_000.0,
                cash=9_000.0,
                market_value=1_000.0,
                total_position_ratio=0.1,
                daily_return=0.0,
                cum_return=0.0,
                drawdown=0.0,
            )
        ]
    )

    report = compare_backtest_to_paper(
        backtest_report_path=backtest_path,
        paper_store_path=tmp_path / "paper.sqlite3",
        trade_date=trade_date,
        tolerance=0.01,
    )

    assert report.status == "DIFF"
    assert report.missing_in_paper_count == 1
    assert report.max_abs_weight_diff == 0.1
    assert "000002.SZ" in render_diff_markdown(report)


def test_compare_backtest_to_paper_writes_reports(tmp_path) -> None:
    backtest_path = tmp_path / "backtest.json"
    backtest_path.write_text(
        json.dumps(
            {
                "rebalance_records": [
                    {
                        "trade_date": "2024-01-31",
                        "target_weights": [{"ts_code": "000001.SZ", "target_weight": 0.10}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    trade_date = date(2024, 1, 31)
    store.save_positions(
        pd.DataFrame(
            [
                {
                    "account_id": "paper",
                    "ts_code": "000001.SZ",
                    "trade_date": trade_date,
                    "quantity": 100,
                    "available_quantity": 100,
                    "avg_cost": 10.0,
                    "market_value": 1000.0,
                    "weight": 1.0,
                }
            ]
        )
    )
    store.save_portfolio_snapshots(
        [
            PortfolioSnapshot(
                account_id="paper",
                trade_date=trade_date,
                total_asset=10_000.0,
                cash=9_000.0,
                market_value=1_000.0,
                total_position_ratio=0.1,
                daily_return=0.0,
                cum_return=0.0,
                drawdown=0.0,
            )
        ]
    )
    report = compare_backtest_to_paper(
        backtest_report_path=backtest_path,
        paper_store_path=tmp_path / "paper.sqlite3",
        trade_date=trade_date,
    )

    json_path = write_diff_json(report, tmp_path / "diff.json")
    markdown_path = write_diff_markdown(report, tmp_path / "diff.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "OK"
    assert "Backtest vs Paper Diff" in markdown_path.read_text(encoding="utf-8")
