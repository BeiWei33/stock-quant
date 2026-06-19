from __future__ import annotations

import json

import pandas as pd

from quant.core.monitoring.stability import (
    StabilityReportBuilder,
    render_stability_markdown,
    write_stability_json,
    write_stability_markdown,
)


def test_stability_report_marks_ready_when_target_window_is_clean(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame(
        [
            _row("2024-09-06", "run-1", "SUCCESS", True),
            _row("2024-09-09", "run-2", "SUCCESS", True),
        ]
    ).to_csv(history_path, index=False)

    report = StabilityReportBuilder(history_path, target_days=2).build()

    assert report.status == "READY"
    assert report.ready_for_live
    assert report.observed_days == 2
    assert report.stable_days == 2
    assert report.progress == 1.0


def test_stability_report_lists_blockers(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame(
        [
            _row(
                "2024-09-09",
                "run-1",
                "SUCCESS",
                True,
                risk_guard_status="REJECTED",
                risk_guard_rejected_orders=1,
                pretrade_gate_status="BLOCK",
                pretrade_gate_failed_count=1,
            )
        ]
    ).to_csv(history_path, index=False)

    report = StabilityReportBuilder(history_path, target_days=20).build()

    assert report.status == "OBSERVING"
    assert not report.ready_for_live
    assert report.unstable_days == 1
    assert report.days[0].blockers == "risk_guard;pretrade_gate"
    assert "risk_guard;pretrade_gate" in render_stability_markdown(report)


def test_stability_report_uses_latest_run_per_trade_date(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    old = _row("2024-09-09", "old-run", "CHECK", False, failed_health_count=1)
    old["recorded_at"] = "2024-09-09T10:00:00+00:00"
    latest = _row("2024-09-09", "latest-run", "SUCCESS", True)
    latest["recorded_at"] = "2024-09-09T11:00:00+00:00"
    pd.DataFrame([old, latest]).to_csv(history_path, index=False)

    report = StabilityReportBuilder(history_path, target_days=1).build()

    assert report.ready_for_live
    assert report.days[0].run_id == "latest-run"
    assert report.days[0].stable


def test_stability_writers_emit_json_and_markdown(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pd.DataFrame([_row("2024-09-09", "run-1", "SUCCESS", True)]).to_csv(
        history_path,
        index=False,
    )
    report = StabilityReportBuilder(history_path, target_days=1).build()

    json_path = write_stability_json(report, tmp_path / "stability.json")
    markdown_path = write_stability_markdown(report, tmp_path / "stability.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "READY"
    assert "Quant Stability Report" in markdown_path.read_text(encoding="utf-8")


def _row(
    trade_date: str,
    run_id: str,
    run_status: str,
    ok: bool,
    *,
    failed_health_count: int = 0,
    data_quality_level: str = "INFO",
    reconciliation_diff_count: int = 0,
    risk_guard_status: str = "OK",
    risk_guard_rejected_orders: int = 0,
    pretrade_gate_status: str = "GO",
    pretrade_gate_failed_count: int = 0,
) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "recorded_at": f"{trade_date}T10:00:00+00:00",
        "run_id": run_id,
        "run_status": run_status,
        "ok": ok,
        "failed_health_count": failed_health_count,
        "failed_health_checks": "",
        "data_quality_level": data_quality_level,
        "reconciliation_diff_count": reconciliation_diff_count,
        "risk_guard_status": risk_guard_status,
        "risk_guard_rejected_orders": risk_guard_rejected_orders,
        "pretrade_gate_status": pretrade_gate_status,
        "pretrade_gate_failed_count": pretrade_gate_failed_count,
    }
