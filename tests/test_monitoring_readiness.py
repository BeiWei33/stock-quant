from __future__ import annotations

import json

from quant.core.monitoring.readiness import (
    build_readiness_report,
    render_readiness_markdown,
    write_readiness_json,
    write_readiness_markdown,
)


def test_readiness_reports_paper_ready_but_not_live_without_qmt_or_20_days(tmp_path) -> None:
    alerts, pretrade, stability = _write_artifacts(
        tmp_path,
        alerts={"status": "OK", "passed": True, "highest_severity": "INFO"},
        pretrade={"status": "GO", "passed": True},
        stability={
            "ready_for_live": False,
            "latest_stable": True,
            "latest_trade_date": "2024-09-09",
            "observed_days": 1,
            "target_days": 20,
            "unstable_days": 0,
        },
    )

    report = build_readiness_report(
        alerts_path=alerts,
        pretrade_gate_path=pretrade,
        stability_path=stability,
        qmt_available=False,
    )

    assert report.status == "PAPER_READY"
    assert report.paper_ready
    assert not report.live_ready
    assert any(check.name == "qmt_interface" and not check.passed for check in report.checks)
    assert any(check.name == "stability_window" and not check.passed for check in report.checks)


def test_readiness_blocks_when_alerts_or_pretrade_fail(tmp_path) -> None:
    alerts, pretrade, stability = _write_artifacts(
        tmp_path,
        alerts={"status": "ALERT", "passed": False, "highest_severity": "CRITICAL"},
        pretrade={"status": "BLOCK", "passed": False},
        stability={
            "ready_for_live": True,
            "latest_stable": True,
            "latest_trade_date": "2024-09-09",
            "observed_days": 20,
            "target_days": 20,
            "unstable_days": 0,
        },
    )

    report = build_readiness_report(
        alerts_path=alerts,
        pretrade_gate_path=pretrade,
        stability_path=stability,
        qmt_available=True,
    )

    assert report.status == "BLOCKED"
    assert not report.paper_ready
    assert not report.live_ready


def test_readiness_reports_live_ready_only_when_all_gates_pass(tmp_path) -> None:
    alerts, pretrade, stability = _write_artifacts(
        tmp_path,
        alerts={"status": "OK", "passed": True, "highest_severity": "INFO"},
        pretrade={"status": "GO", "passed": True},
        stability={
            "ready_for_live": True,
            "latest_stable": True,
            "latest_trade_date": "2024-09-09",
            "observed_days": 20,
            "target_days": 20,
            "unstable_days": 0,
        },
    )

    report = build_readiness_report(
        alerts_path=alerts,
        pretrade_gate_path=pretrade,
        stability_path=stability,
        qmt_available=True,
    )

    assert report.status == "LIVE_READY"
    assert report.paper_ready
    assert report.live_ready


def test_readiness_writers_emit_json_and_markdown(tmp_path) -> None:
    alerts, pretrade, stability = _write_artifacts(
        tmp_path,
        alerts={"status": "OK", "passed": True, "highest_severity": "INFO"},
        pretrade={"status": "GO", "passed": True},
        stability={
            "ready_for_live": False,
            "latest_stable": True,
            "latest_trade_date": "2024-09-09",
            "observed_days": 1,
            "target_days": 20,
            "unstable_days": 0,
        },
    )
    report = build_readiness_report(
        alerts_path=alerts,
        pretrade_gate_path=pretrade,
        stability_path=stability,
    )

    json_path = write_readiness_json(report, tmp_path / "readiness.json")
    markdown_path = write_readiness_markdown(report, tmp_path / "readiness.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "PAPER_READY"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Quant Readiness Report" in markdown
    assert "qmt_interface" in render_readiness_markdown(report)


def _write_artifacts(
    tmp_path,
    *,
    alerts: dict[str, object],
    pretrade: dict[str, object],
    stability: dict[str, object],
):
    alerts_path = tmp_path / "alerts.json"
    pretrade_path = tmp_path / "pretrade_gate.json"
    stability_path = tmp_path / "stability.json"
    alerts_path.write_text(json.dumps(alerts), encoding="utf-8")
    pretrade_path.write_text(json.dumps(pretrade), encoding="utf-8")
    stability_path.write_text(json.dumps(stability), encoding="utf-8")
    return alerts_path, pretrade_path, stability_path
