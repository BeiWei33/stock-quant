from __future__ import annotations

import json

from quant.core.reporting.execution_report import (
    ExecutionReportPaths,
    build_execution_day_end_report,
    render_execution_day_end_markdown,
    write_execution_day_end_json,
    write_execution_day_end_markdown,
)


def test_execution_day_end_report_marks_pending_manual_when_fills_are_unvalidated(tmp_path) -> None:
    paths = _write_clean_artifacts(tmp_path)

    report = build_execution_day_end_report(paths)

    assert report.status == "PENDING_MANUAL"
    assert report.trade_date == "2024-09-09"
    assert report.strategy_id == "momentum_rank"
    assert report.order_count == 1
    assert report.estimated_notional == 1050.0
    assert any(artifact.name == "manual_fill_validation" and artifact.status == "PENDING" for artifact in report.artifacts)
    assert "Execution Day-End Report" in render_execution_day_end_markdown(report)


def test_execution_day_end_report_blocks_on_validation_error(tmp_path) -> None:
    paths = _write_clean_artifacts(tmp_path)
    paths.manual_fill_validation.write_text(
        json.dumps({"status": "ERROR", "passed": False, "issues": [{"field": "status"}]}),
        encoding="utf-8",
    )

    report = build_execution_day_end_report(paths)

    assert report.status == "BLOCKED"
    assert any(artifact.name == "manual_fill_validation" and artifact.status == "ERROR" for artifact in report.artifacts)


def test_execution_day_end_report_writers_emit_json_and_markdown(tmp_path) -> None:
    paths = _write_clean_artifacts(tmp_path)
    report = build_execution_day_end_report(paths)

    json_path = write_execution_day_end_json(report, tmp_path / "execution_day_end.json")
    markdown_path = write_execution_day_end_markdown(report, tmp_path / "execution_day_end.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "PENDING_MANUAL"
    assert "manual_execution" in markdown_path.read_text(encoding="utf-8")


def _write_clean_artifacts(tmp_path) -> ExecutionReportPaths:
    paths = ExecutionReportPaths(
        paper_plan=tmp_path / "paper_plan.json",
        risk_guard=tmp_path / "risk_guard.json",
        broker_submission=tmp_path / "broker_submission.json",
        execution_authorization=tmp_path / "execution_authorization.json",
        broker_adapter_contract=tmp_path / "broker_adapter_contract.json",
        manual_execution=tmp_path / "manual_execution.json",
        pretrade_gate=tmp_path / "pretrade_gate.json",
        manual_fill_validation=tmp_path / "missing_manual_fill_validation.json",
        manual_reconciliation=tmp_path / "missing_manual_reconciliation.json",
        monitor_status=tmp_path / "status_summary.json",
        readiness=tmp_path / "readiness.json",
    )
    paths.paper_plan.write_text(
        json.dumps(
            {
                "trade_date": "2024-09-09",
                "strategy": {"strategy_id": "momentum_rank"},
                "order_intents": [{"quantity": 100, "price": 10.5}],
            }
        ),
        encoding="utf-8",
    )
    paths.risk_guard.write_text(
        json.dumps({"allowed": True, "accepted_orders": 1, "rejected_orders": 0}),
        encoding="utf-8",
    )
    paths.broker_submission.write_text(
        json.dumps(
            {
                "mode": "DRY_RUN",
                "risk_guard_allowed": True,
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "order_count": 1,
                "orders": [{"quantity": 100, "price": 10.5}],
            }
        ),
        encoding="utf-8",
    )
    paths.execution_authorization.write_text(
        json.dumps({"passed": True, "mode": "DRY_RUN", "adapter": "dry_run"}),
        encoding="utf-8",
    )
    paths.broker_adapter_contract.write_text(
        json.dumps({"status": "OK", "passed": True, "adapter": "dry_run", "mode": "DRY_RUN", "submitted": False}),
        encoding="utf-8",
    )
    paths.manual_execution.write_text(
        json.dumps(
            {
                "status": "READY",
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "order_count": 1,
                "estimated_notional": 1050.0,
            }
        ),
        encoding="utf-8",
    )
    paths.pretrade_gate.write_text(
        json.dumps({"status": "GO", "passed": True, "checks": []}),
        encoding="utf-8",
    )
    paths.monitor_status.write_text(
        json.dumps({"level": "INFO", "latest_trade_date": "2024-09-09"}),
        encoding="utf-8",
    )
    paths.readiness.write_text(
        json.dumps({"status": "PAPER_READY", "paper_ready": True, "live_ready": False}),
        encoding="utf-8",
    )
    return paths
