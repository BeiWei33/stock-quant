from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pandas as pd

from quant.core.models import (
    OrderFill,
    OrderIntent,
    OrderRiskResult,
    PortfolioSnapshot,
    RiskDecision,
    WorkflowRun,
)
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.reporting.daily_report import DailyReportGenerator
from quant.core.reconciliation.trades import reconcile_trade_activity


def test_daily_report_aggregates_summary_account_state_and_alpha(tmp_path) -> None:
    trade_date = date(2024, 9, 9)
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    order = OrderIntent(
        account_id="paper",
        strategy_id="momentum_rank",
        trade_date=trade_date,
        ts_code="000001.SZ",
        side="BUY",
        quantity=100,
        price=10.0,
        target_weight=0.1,
        reason="rebalance",
    )
    fill = OrderFill(
        fill_id="fill-1",
        order_id=order.order_id,
        account_id="paper",
        strategy_id="momentum_rank",
        ts_code="000001.SZ",
        side="BUY",
        price=10.0,
        quantity=100,
        amount=1000.0,
        fee=5.0,
        tax=0.0,
        trade_date=trade_date,
    )
    snapshot = PortfolioSnapshot(
        account_id="paper",
        trade_date=trade_date,
        total_asset=100_100.0,
        cash=99_095.0,
        market_value=1_005.0,
        total_position_ratio=0.01004,
        daily_return=0.001,
        cum_return=0.001,
        drawdown=0.0,
    )
    store.save_order_intents([order])
    store.save_order_risk_results([OrderRiskResult(order=order, decision=RiskDecision.allow())])
    store.save_order_fills([fill])
    store.save_positions(
        pd.DataFrame(
            [
                {
                    "account_id": "paper",
                    "ts_code": "000001.SZ",
                    "trade_date": trade_date,
                    "quantity": 100,
                    "available_quantity": 0,
                    "avg_cost": 10.0,
                    "market_value": 1_005.0,
                    "weight": 0.01004,
                }
            ]
        )
    )
    store.save_portfolio_snapshots([snapshot])
    store.save_workflow_run(
        WorkflowRun(
            run_id="run-1",
            workflow_name="daily",
            status="SUCCESS",
            started_at=datetime(2024, 9, 9, 9, tzinfo=UTC),
            ended_at=datetime(2024, 9, 9, 9, 1, tzinfo=UTC),
            trade_date=trade_date,
            summary_path=str(tmp_path / "daily_summary.json"),
        )
    )
    store.save_trade_reconciliation_report(
        reconcile_trade_activity(
            account_id="paper",
            trade_date=trade_date,
            local_orders=pd.DataFrame([{"ts_code": "000001.SZ", "side": "BUY", "quantity": 100}]),
            broker_orders=pd.DataFrame([{"ts_code": "000001.SZ", "side": "BUY", "quantity": 0}]),
        )
    )

    alpha_path = tmp_path / "alpha.json"
    alpha_path.write_text(
        json.dumps(
            {
                "factor_name": "momentum_60d",
                "horizon": 5,
                "quantiles": 5,
                "summary": {
                    "ic_mean": 0.12,
                    "icir": 1.2,
                    "rank_ic_mean": 0.1,
                    "rank_icir": 1.0,
                    "rank_ic_positive_rate": 0.6,
                    "sample_days": 20,
                    "top_group_return_mean": 0.02,
                    "bottom_group_return_mean": -0.01,
                    "long_short_return_mean": 0.03,
                    "group_monotonicity": 0.8,
                    "top_quantile_turnover_mean": 0.15,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    summary_path = tmp_path / "daily_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "trade_date": trade_date.isoformat(),
                "collected_stocks": 30,
                "collected_daily_bars": 5400,
                "collected_benchmark_bars": 180,
                "research_json_path": str(alpha_path),
                "research_markdown_path": str(tmp_path / "alpha.md"),
                "order_count": 1,
                "rejected_order_count": 0,
                "fill_count": 1,
                "fill_rejected_count": 0,
                "snapshot": snapshot.to_dict(),
                "health_checks": [{"name": "portfolio_snapshot_created", "ok": True, "detail": ""}],
                "ok": True,
                "run_id": "run-1",
                "run_status": "SUCCESS",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = DailyReportGenerator(
        summary_path=summary_path,
        paper_store_path=tmp_path / "paper.sqlite3",
    ).generate(
        markdown_path=tmp_path / "daily_report.md",
        html_path=tmp_path / "daily_report.html",
    )

    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "每日量化报告 - 2024-09-09" in markdown
    assert "默认 `python -m quant.apps.start` / `daily` 使用本地样例数据" in markdown
    assert "SUCCESS" in markdown
    assert "100,100.00" in markdown
    assert "000001.SZ" in markdown
    assert "对账" in markdown
    assert "paper:2024-09-09:trades" in markdown
    assert "momentum_60d" in markdown
    assert "多空平均收益" in markdown
    assert (tmp_path / "daily_report.html").exists()


def test_daily_report_shows_akshare_data_mode_note(tmp_path) -> None:
    trade_date = date(2024, 9, 9)
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    summary_path = tmp_path / "daily_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "trade_date": trade_date.isoformat(),
                "market_data_mode": {
                    "label": "AkShare 真实 A 股行情",
                    "note": "通过 AkShare 获取公开 A 股行情数据，仅用于研究和模拟盘。",
                },
                "health_checks": [],
                "run_status": "SUCCESS",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = DailyReportGenerator(
        summary_path=summary_path,
        paper_store_path=tmp_path / "paper.sqlite3",
    ).generate(markdown_path=tmp_path / "daily_report.md")

    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "AkShare 真实 A 股行情" in markdown
    assert "仅用于研究和模拟盘" in markdown
