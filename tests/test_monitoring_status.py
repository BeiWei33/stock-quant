from __future__ import annotations

import json

import pandas as pd

from quant.core.monitoring.status import (
    MonitorStatusBuilder,
    render_status_markdown,
    write_status_json,
    write_status_markdown,
)


def test_monitor_status_builder_summarizes_recent_history(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-06",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "order_count": 2,
                "rejected_order_count": 0,
                "fill_count": 2,
                "fill_rejected_count": 0,
                "data_quality_level": "INFO",
                "data_quality_issue_count": 0,
                "data_cleaning_changed_rows": 0,
                "reconciliation_status": "OK",
                "reconciliation_diff_count": 0,
                "risk_guard_status": "OK",
                "risk_guard_rejected_orders": 0,
                "pretrade_gate_status": "GO",
                "pretrade_gate_passed": True,
                "pretrade_gate_failed_count": 0,
                "pretrade_gate_failed_checks": "",
                "total_asset": 1000000.0,
                "daily_return": 0.0,
                "drawdown": 0.0,
                "total_position_ratio": 0.2,
                "failed_health_count": 0,
                "failed_health_checks": "",
            },
            {
                "trade_date": "2024-09-09",
                "run_id": "run-2",
                "run_status": "SUCCESS",
                "ok": True,
                "order_count": 3,
                "rejected_order_count": 1,
                "fill_count": 2,
                "fill_rejected_count": 1,
                "data_quality_level": "INFO",
                "data_quality_issue_count": 0,
                "data_cleaning_changed_rows": 7,
                "reconciliation_status": "OK",
                "reconciliation_diff_count": 0,
                "risk_guard_status": "OK",
                "risk_guard_rejected_orders": 0,
                "pretrade_gate_status": "GO",
                "pretrade_gate_passed": True,
                "pretrade_gate_failed_count": 0,
                "pretrade_gate_failed_checks": "",
                "total_asset": 1001000.0,
                "daily_return": 0.001,
                "drawdown": -0.01,
                "total_position_ratio": 0.3,
                "failed_health_count": 0,
                "failed_health_checks": "",
            },
        ]
    ).to_csv(history_path, index=False)

    summary = MonitorStatusBuilder(history_path, limit=20).build()

    assert summary.level == "INFO"
    assert summary.latest_trade_date == "2024-09-09"
    assert summary.success_rate == 1.0
    assert summary.total_orders == 5
    assert summary.total_rejected_fills == 1
    assert summary.latest_data_quality_level == "INFO"
    assert summary.data_cleaning_changed_rows == 7
    assert summary.latest_reconciliation_status == "OK"
    assert summary.latest_risk_guard_status == "OK"
    assert summary.risk_guard_rejected_runs == 0
    assert summary.latest_pretrade_gate_status == "GO"
    assert summary.latest_pretrade_gate_passed
    assert summary.pretrade_gate_block_runs == 0
    assert summary.max_drawdown == -0.01


def test_monitor_status_marks_unhealthy_window_as_warning_or_critical(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-06",
                "run_id": "run-1",
                "run_status": "CHECK",
                "ok": False,
                "failed_health_count": 1,
                "failed_health_checks": "data",
                "data_quality_level": "WARNING",
                "data_quality_issue_count": 1,
                "reconciliation_status": "DIFF",
                "reconciliation_diff_count": 2,
                "risk_guard_status": "OK",
                "risk_guard_rejected_orders": 0,
                "pretrade_gate_status": "GO",
                "pretrade_gate_passed": True,
                "pretrade_gate_failed_count": 0,
                "pretrade_gate_failed_checks": "",
            },
            {
                "trade_date": "2024-09-09",
                "run_id": "run-2",
                "run_status": "FAILED",
                "ok": False,
                "failed_health_count": 1,
                "failed_health_checks": "workflow",
                "data_quality_level": "ERROR",
                "data_quality_issue_count": 2,
                "reconciliation_status": "OK",
                "reconciliation_diff_count": 0,
                "risk_guard_status": "REJECTED",
                "risk_guard_rejected_orders": 2,
                "pretrade_gate_status": "BLOCK",
                "pretrade_gate_passed": False,
                "pretrade_gate_failed_count": 1,
                "pretrade_gate_failed_checks": "risk_guard_allowed",
            },
        ]
    ).to_csv(history_path, index=False)

    summary = MonitorStatusBuilder(history_path, limit=20).build()

    assert summary.level == "CRITICAL"
    assert summary.failed_runs == 1
    assert summary.consecutive_unhealthy_runs == 2
    assert summary.data_quality_error_runs == 1
    assert summary.data_quality_warning_runs == 1
    assert summary.data_quality_issue_count == 3
    assert summary.reconciliation_diff_runs == 1
    assert summary.reconciliation_diff_count == 2
    assert summary.latest_risk_guard_status == "REJECTED"
    assert summary.risk_guard_rejected_runs == 1
    assert summary.risk_guard_rejected_orders == 2
    assert summary.latest_pretrade_gate_status == "BLOCK"
    assert not summary.latest_pretrade_gate_passed
    assert summary.pretrade_gate_block_runs == 1
    assert summary.pretrade_gate_failed_count == 1
    assert summary.pretrade_gate_failed_checks == "risk_guard_allowed"
    assert summary.failed_health_checks == "data;workflow"


def test_monitor_status_reports_pretrade_gate_block_without_self_escalation(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "failed_health_count": 0,
                "failed_health_checks": "",
                "data_quality_level": "INFO",
                "data_quality_issue_count": 0,
                "reconciliation_status": "OK",
                "reconciliation_diff_count": 0,
                "risk_guard_status": "OK",
                "risk_guard_rejected_orders": 0,
                "pretrade_gate_status": "BLOCK",
                "pretrade_gate_passed": False,
                "pretrade_gate_failed_count": 1,
                "pretrade_gate_failed_checks": "monitor_status",
            }
        ]
    ).to_csv(history_path, index=False)

    summary = MonitorStatusBuilder(history_path, limit=20).build()

    assert summary.level == "INFO"
    assert summary.consecutive_unhealthy_runs == 0
    assert summary.pretrade_gate_block_runs == 1
    assert summary.pretrade_gate_failed_checks == "monitor_status"


def test_monitor_status_uses_latest_run_per_trade_date_by_default(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "recorded_at": "2024-09-09T10:00:00+00:00",
                "run_id": "old-run",
                "run_status": "CHECK",
                "ok": False,
                "failed_health_count": 1,
                "failed_health_checks": "data_quality_ok",
                "data_quality_level": "WARNING",
            },
            {
                "trade_date": "2024-09-09",
                "recorded_at": "2024-09-09T11:00:00+00:00",
                "run_id": "latest-run",
                "run_status": "SUCCESS",
                "ok": True,
                "failed_health_count": 0,
                "failed_health_checks": "",
                "data_quality_level": "INFO",
            },
        ]
    ).to_csv(history_path, index=False)

    latest_only = MonitorStatusBuilder(history_path).build()
    all_runs = MonitorStatusBuilder(history_path, latest_per_trade_date=False).build()

    assert latest_only.level == "INFO"
    assert latest_only.latest_run_id == "latest-run"
    assert latest_only.total_runs == 1
    assert latest_only.failed_health_count == 0
    assert all_runs.level == "WARNING"
    assert all_runs.total_runs == 2
    assert all_runs.failed_health_checks == "data_quality_ok"


def test_monitor_status_writes_json_and_markdown(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "total_asset": 100.0,
                "daily_return": 0.01,
                "drawdown": 0.0,
                "total_position_ratio": 0.1,
            }
        ]
    ).to_csv(history_path, index=False)
    summary = MonitorStatusBuilder(history_path).build()
    json_path = write_status_json(summary, tmp_path / "status.json")
    markdown_path = write_status_markdown(summary, tmp_path / "status.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["level"] == "INFO"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Quant Monitor Status - 2024-09-09" in markdown
    assert "Latest Data Quality" in markdown
    assert "Latest Reconciliation" in markdown
    assert "Latest Risk Guard" in markdown
    assert "Latest Pre-Trade Gate" in markdown
    assert "Success Rate" in render_status_markdown(summary)
