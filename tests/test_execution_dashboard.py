from __future__ import annotations

import json

from quant.core.reporting.execution_dashboard import (
    ExecutionDashboardPaths,
    build_execution_dashboard,
    write_execution_dashboard_html,
)


def test_execution_dashboard_renders_combined_status(tmp_path) -> None:
    paths = ExecutionDashboardPaths(
        execution_day_end=tmp_path / "execution_day_end.json",
        config_health=tmp_path / "config_health.json",
        readiness=tmp_path / "readiness.json",
        audit_report=tmp_path / "execution_audit_report.json",
    )
    paths.execution_day_end.write_text(
        json.dumps(
            {
                "status": "BLOCKED",
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "artifacts": [
                    {
                        "name": "manual_fill_validation",
                        "status": "ERROR",
                        "passed": False,
                        "detail": "issues=3",
                        "path": "manual_fill_validation.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    paths.config_health.write_text(
        json.dumps(
            {
                "status": "WARNING",
                "checks": [{"name": "config", "status": "OK", "severity": "INFO", "detail": "fine"}],
            }
        ),
        encoding="utf-8",
    )
    paths.readiness.write_text(json.dumps({"status": "PAPER_READY"}), encoding="utf-8")
    paths.audit_report.write_text(
        json.dumps(
            {
                "status": "BLOCKED",
                "steps": [
                    {
                        "event_type": "manual_fill_validation",
                        "status": "ERROR",
                        "passed": False,
                        "detail": "issues=3",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    dashboard = build_execution_dashboard(paths)
    html_path = write_execution_dashboard_html(dashboard, tmp_path / "dashboard.html")

    html = html_path.read_text(encoding="utf-8")
    assert dashboard.status == "BLOCKED"
    assert "Execution Control" in html
    assert "manual_fill_validation" in html
    assert "momentum_rank" in html
