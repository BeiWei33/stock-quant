from __future__ import annotations

import json

from quant.core.monitoring.alerts import (
    evaluate_monitor_alerts,
    render_alerts_markdown,
    write_alerts_json,
    write_alerts_markdown,
)


def test_monitor_alerts_pass_clean_status(tmp_path) -> None:
    status_path = tmp_path / "status_summary.json"
    status_path.write_text(
        json.dumps(
            {
                "level": "INFO",
                "latest_pretrade_gate_status": "GO",
                "pretrade_gate_block_runs": 0,
                "risk_guard_rejected_runs": 0,
                "risk_guard_rejected_orders": 0,
                "reconciliation_diff_runs": 0,
                "reconciliation_diff_count": 0,
                "failed_health_count": 0,
                "max_drawdown": -0.03,
            }
        ),
        encoding="utf-8",
    )

    evaluation = evaluate_monitor_alerts(status_path)

    assert evaluation.status == "OK"
    assert evaluation.passed
    assert evaluation.highest_severity == "INFO"
    assert all(alert.passed for alert in evaluation.alerts)


def test_monitor_alerts_raise_critical_for_blocked_gate(tmp_path) -> None:
    status_path = tmp_path / "status_summary.json"
    status_path.write_text(
        json.dumps(
            {
                "level": "CRITICAL",
                "latest_pretrade_gate_status": "BLOCK",
                "pretrade_gate_block_runs": 1,
                "pretrade_gate_failed_checks": "monitor_status",
                "risk_guard_rejected_runs": 0,
                "risk_guard_rejected_orders": 0,
                "reconciliation_diff_runs": 0,
                "reconciliation_diff_count": 0,
                "failed_health_count": 1,
                "failed_health_checks": "data_quality_ok",
                "max_drawdown": -0.02,
            }
        ),
        encoding="utf-8",
    )

    evaluation = evaluate_monitor_alerts(status_path)
    failed = {alert.name: alert for alert in evaluation.alerts if not alert.passed}

    assert evaluation.status == "ALERT"
    assert not evaluation.passed
    assert evaluation.highest_severity == "CRITICAL"
    assert failed["monitor_level"].severity == "CRITICAL"
    assert failed["pretrade_gate"].severity == "CRITICAL"
    assert "monitor_status" in failed["pretrade_gate"].detail
    assert failed["health_checks"].severity == "WARNING"


def test_monitor_alerts_writers_emit_json_and_markdown(tmp_path) -> None:
    status_path = tmp_path / "status_summary.json"
    status_path.write_text(
        json.dumps(
            {
                "level": "WARNING",
                "latest_pretrade_gate_status": "GO",
                "pretrade_gate_block_runs": 0,
                "risk_guard_rejected_runs": 1,
                "risk_guard_rejected_orders": 2,
                "reconciliation_diff_runs": 0,
                "reconciliation_diff_count": 0,
                "failed_health_count": 0,
                "max_drawdown": -0.11,
            }
        ),
        encoding="utf-8",
    )
    evaluation = evaluate_monitor_alerts(status_path)

    json_path = write_alerts_json(evaluation, tmp_path / "alerts.json")
    markdown_path = write_alerts_markdown(evaluation, tmp_path / "alerts.md")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["status"] == "ALERT"
    assert "risk_guard" in markdown
    assert "drawdown" in render_alerts_markdown(evaluation)
