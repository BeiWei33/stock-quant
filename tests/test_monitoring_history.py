from __future__ import annotations

import json

import pandas as pd

from quant.core.monitoring.history import (
    DailyMonitorCsvStore,
    DailyMonitorJsonlStore,
    DailyMonitorRecordBuilder,
)


def test_daily_monitor_record_builder_extracts_summary_metrics(tmp_path) -> None:
    summary_path = tmp_path / "daily_summary.json"
    quality_path = tmp_path / "data_quality.json"
    cleaning_path = tmp_path / "data_cleaning.json"
    reconciliation_path = tmp_path / "trade_reconciliation.json"
    risk_guard_audit_path = tmp_path / "risk_guard_audit.jsonl"
    pretrade_gate_path = tmp_path / "pretrade_gate.json"
    quality_path.write_text(
        json.dumps(
            {
                "ok": False,
                "level": "ERROR",
                "issues": [
                    {"issue_type": "OHLC_INCONSISTENT", "severity": "ERROR", "count": 3},
                    {"issue_type": "QUALITY_FLAG_REVIEW", "severity": "WARNING", "count": 1},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cleaning_path.write_text(
        json.dumps({"changed_rows": 7, "high_fixed_count": 4, "low_fixed_count": 3}),
        encoding="utf-8",
    )
    reconciliation_path.write_text(
        json.dumps(
            {
                "status": "DIFF",
                "order_differences": [{"ts_code": "000001.SZ"}],
                "fill_differences": [{"ts_code": "000002.SZ"}],
            }
        ),
        encoding="utf-8",
    )
    risk_guard_audit_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "RiskGuardRun",
                        "epoch_seconds": 1700000000,
                        "allowed": True,
                        "input_orders": 1,
                        "rejected_orders": 0,
                    }
                ),
                json.dumps(
                    {
                        "event_type": "RiskGuardRun",
                        "epoch_seconds": 1700000300,
                        "allowed": False,
                        "input_orders": 3,
                        "rejected_orders": 1,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    pretrade_gate_path.write_text(
        json.dumps(
            {
                "status": "BLOCK",
                "passed": False,
                "checks": [
                    {"name": "monitor_status", "passed": False, "severity": "WARNING"},
                    {"name": "risk_guard_allowed", "passed": True, "severity": "CRITICAL"},
                ],
            }
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(
            {
                "trade_date": "2024-09-09",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "collected_stocks": 30,
                "collected_daily_bars": 5400,
                "collected_benchmark_bars": 180,
                "order_count": 3,
                "rejected_order_count": 1,
                "fill_count": 2,
                "fill_rejected_count": 1,
                "data_quality_json_path": str(quality_path),
                "data_quality_level": "ERROR",
                "snapshot": {
                    "total_asset": 1000100.0,
                    "cash": 700000.0,
                    "market_value": 300100.0,
                    "total_position_ratio": 0.3,
                    "daily_return": 0.001,
                    "cum_return": 0.01,
                    "drawdown": -0.02,
                    "excess_return": 0.003,
                },
                "health_checks": [
                    {"name": "data", "ok": True, "detail": ""},
                    {"name": "report", "ok": False, "detail": "missing"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    record = DailyMonitorRecordBuilder(
        summary_path,
        reconciliation_report_path=reconciliation_path,
        risk_guard_audit_path=risk_guard_audit_path,
        pretrade_gate_report_path=pretrade_gate_path,
    ).build()

    assert record.trade_date == "2024-09-09"
    assert record.run_id == "run-1"
    assert record.total_asset == 1000100.0
    assert record.data_quality_level == "ERROR"
    assert not record.data_quality_ok
    assert record.data_quality_issue_count == 2
    assert record.data_quality_error_count == 1
    assert record.data_quality_warning_count == 1
    assert record.data_cleaning_changed_rows == 7
    assert record.data_cleaning_high_fixed_count == 4
    assert record.data_cleaning_low_fixed_count == 3
    assert record.reconciliation_status == "DIFF"
    assert record.reconciliation_diff_count == 2
    assert record.reconciliation_order_diff_count == 1
    assert record.reconciliation_fill_diff_count == 1
    assert record.risk_guard_status == "REJECTED"
    assert not record.risk_guard_allowed
    assert record.risk_guard_input_orders == 3
    assert record.risk_guard_rejected_orders == 1
    assert record.risk_guard_epoch_seconds == 1700000300
    assert record.pretrade_gate_status == "BLOCK"
    assert not record.pretrade_gate_passed
    assert record.pretrade_gate_failed_count == 1
    assert record.pretrade_gate_failed_checks == "monitor_status"
    assert record.failed_health_count == 1
    assert record.failed_health_checks == "report"


def test_daily_monitor_csv_store_upserts_by_run_id(tmp_path) -> None:
    summary_path = tmp_path / "daily_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "trade_date": "2024-09-09",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "snapshot": {"total_asset": 100.0},
            }
        ),
        encoding="utf-8",
    )
    record = DailyMonitorRecordBuilder(summary_path).build()
    csv_path = tmp_path / "daily_history.csv"

    DailyMonitorCsvStore(csv_path).upsert(record)
    DailyMonitorCsvStore(csv_path).upsert(record)

    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert not (tmp_path / ".daily_history.csv.tmp").exists()
    assert df.iloc[0]["run_id"] == "run-1"
    assert df.iloc[0]["total_asset"] == 100.0


def test_daily_monitor_jsonl_store_appends_audit_records(tmp_path) -> None:
    summary_path = tmp_path / "daily_summary.json"
    summary_path.write_text(
        json.dumps({"trade_date": "2024-09-09", "run_id": "run-1", "run_status": "SUCCESS"}),
        encoding="utf-8",
    )
    record = DailyMonitorRecordBuilder(summary_path).build()
    jsonl_path = tmp_path / "daily_history.jsonl"

    DailyMonitorJsonlStore(jsonl_path).append(record)
    DailyMonitorJsonlStore(jsonl_path).append(record)

    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["trade_date"] == "2024-09-09"
