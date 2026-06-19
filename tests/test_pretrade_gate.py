from __future__ import annotations

import json

from quant.core.execution.preflight import build_pretrade_gate_report, render_pretrade_gate_markdown


def _write(path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pretrade_gate_passes_clean_artifacts(tmp_path) -> None:
    monitor = tmp_path / "status.json"
    risk = tmp_path / "risk.json"
    broker = tmp_path / "broker.json"
    _write(monitor, {"level": "INFO"})
    _write(risk, {"allowed": True, "accepted_orders": 2, "rejected_orders": 0})
    _write(broker, {"risk_guard_allowed": True, "order_count": 2, "mode": "DRY_RUN", "adapter": "dry_run"})

    report = build_pretrade_gate_report(
        monitor_status_path=monitor,
        risk_guard_path=risk,
        broker_submission_path=broker,
    )

    assert report.passed
    assert report.status == "GO"
    assert all(check.passed for check in report.checks)
    assert "Pre-Trade Gate Report" in render_pretrade_gate_markdown(report)


def test_pretrade_gate_blocks_monitor_warning_by_default(tmp_path) -> None:
    monitor = tmp_path / "status.json"
    risk = tmp_path / "risk.json"
    broker = tmp_path / "broker.json"
    _write(monitor, {"level": "WARNING"})
    _write(risk, {"allowed": True, "accepted_orders": 1, "rejected_orders": 0})
    _write(broker, {"risk_guard_allowed": True, "order_count": 1, "mode": "DRY_RUN", "adapter": "dry_run"})

    report = build_pretrade_gate_report(
        monitor_status_path=monitor,
        risk_guard_path=risk,
        broker_submission_path=broker,
    )

    assert not report.passed
    assert report.status == "BLOCK"
    assert any(check.name == "monitor_status" and not check.passed for check in report.checks)


def test_pretrade_gate_blocks_order_count_mismatch(tmp_path) -> None:
    monitor = tmp_path / "status.json"
    risk = tmp_path / "risk.json"
    broker = tmp_path / "broker.json"
    _write(monitor, {"level": "INFO"})
    _write(risk, {"allowed": True, "accepted_orders": 2, "rejected_orders": 0})
    _write(broker, {"risk_guard_allowed": True, "order_count": 1, "mode": "DRY_RUN", "adapter": "dry_run"})

    report = build_pretrade_gate_report(
        monitor_status_path=monitor,
        risk_guard_path=risk,
        broker_submission_path=broker,
    )

    assert not report.passed
    assert any(check.name == "order_count_match" and not check.passed for check in report.checks)


def test_pretrade_gate_blocks_live_submission_without_execution_policy(tmp_path) -> None:
    monitor = tmp_path / "status.json"
    risk = tmp_path / "risk.json"
    broker = tmp_path / "broker.json"
    _write(monitor, {"level": "INFO"})
    _write(risk, {"allowed": True, "accepted_orders": 1, "rejected_orders": 0})
    _write(
        broker,
        {
            "risk_guard_allowed": True,
            "order_count": 1,
            "mode": "LIVE",
            "adapter": "qmt",
            "trade_date": "2024-09-09",
            "strategy_id": "momentum_rank",
            "orders": [{"quantity": 100, "price": 10.0}],
        },
    )

    report = build_pretrade_gate_report(
        monitor_status_path=monitor,
        risk_guard_path=risk,
        broker_submission_path=broker,
    )

    assert not report.passed
    assert any(
        check.name == "execution_execution_mode_allowed" and not check.passed
        for check in report.checks
    )
