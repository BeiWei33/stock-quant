from __future__ import annotations

import json
from datetime import UTC, datetime

from quant.core.execution.audit import (
    append_execution_audit,
    build_execution_audit_event,
    build_execution_audit_report,
    read_execution_audit_events,
    render_execution_audit_report_markdown,
    write_execution_audit_report_json,
    write_execution_audit_report_markdown,
)


def test_execution_audit_event_extracts_execution_summary(tmp_path) -> None:
    event = build_execution_audit_event(
        event_type="manual_package",
        payload={
            "status": "READY",
            "trade_date": "2024-09-09",
            "strategy_id": "momentum_rank",
            "order_count": 2,
            "estimated_notional": 1234.5,
        },
        artifact_paths={"json": tmp_path / "manual_execution.json"},
        summary={"package_id": "pkg-1"},
        timestamp=datetime(2024, 9, 9, tzinfo=UTC),
    )

    assert event.status == "READY"
    assert event.passed is True
    assert event.trade_date == "2024-09-09"
    assert event.strategy_id == "momentum_rank"
    assert event.order_count == 2
    assert event.notional == 1234.5
    assert event.artifact_paths["json"].endswith("manual_execution.json")


def test_execution_audit_jsonl_appends_and_reads_events(tmp_path) -> None:
    audit_log = tmp_path / "execution_audit.jsonl"

    append_execution_audit(
        event_type="manual_fill_validation",
        payload={
            "status": "ERROR",
            "passed": False,
            "order_count": 1,
            "total_fill_amount": 0,
            "issues": [{"field": "status"}],
        },
        path=audit_log,
        artifact_paths={"json": tmp_path / "manual_fill_validation.json"},
        summary={"issue_count": 1},
    )

    lines = audit_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    raw = json.loads(lines[0])
    assert raw["event_type"] == "manual_fill_validation"
    assert raw["status"] == "ERROR"
    assert raw["passed"] is False
    assert raw["summary"]["issue_count"] == 1

    events = read_execution_audit_events(audit_log)
    assert len(events) == 1
    assert events[0].event_type == "manual_fill_validation"
    assert events[0].passed is False


def test_execution_audit_report_summarizes_latest_refresh_cycle(tmp_path) -> None:
    audit_log = tmp_path / "execution_audit.jsonl"
    for event_type, status, passed in [
        ("execution_authorization", "GO", True),
        ("broker_adapter_contract", "OK", True),
        ("manual_package_existing", "READY", True),
        ("manual_fill_validation", "ERROR", False),
        ("manual_reconciliation", "SKIPPED", None),
        ("execution_day_end", "BLOCKED", False),
        ("config_health", "WARNING", True),
    ]:
        append_execution_audit(
            event_type=event_type,
            payload={
                "status": status,
                "passed": passed,
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "order_count": 3,
            },
            path=audit_log,
            summary={"issue_count": 3} if event_type == "manual_fill_validation" else {},
        )

    report = build_execution_audit_report(read_execution_audit_events(audit_log))

    assert report.status == "BLOCKED"
    assert report.trade_date == "2024-09-09"
    assert report.strategy_id == "momentum_rank"
    assert report.step_count == 7
    assert any(step.event_type == "manual_package" and step.status == "READY" for step in report.steps)
    assert "Execution Audit Report" in render_execution_audit_report_markdown(report)

    json_path = write_execution_audit_report_json(report, tmp_path / "execution_audit_report.json")
    md_path = write_execution_audit_report_markdown(report, tmp_path / "execution_audit_report.md")
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "BLOCKED"
    assert "manual_fill_validation" in md_path.read_text(encoding="utf-8")
