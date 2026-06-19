from __future__ import annotations

import json

import pandas as pd

from quant.core.monitoring.refresh import MonitorRefreshPaths, refresh_monitoring


def test_refresh_monitoring_writes_derived_artifacts(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pretrade_path = tmp_path / "pretrade_gate.json"
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "recorded_at": "2024-09-09T10:00:00+00:00",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "order_count": 3,
                "rejected_order_count": 0,
                "fill_count": 3,
                "fill_rejected_count": 0,
                "data_quality_level": "INFO",
                "data_quality_issue_count": 0,
                "data_cleaning_changed_rows": 10,
                "reconciliation_status": "OK",
                "reconciliation_diff_count": 0,
                "risk_guard_status": "OK",
                "risk_guard_rejected_orders": 0,
                "pretrade_gate_status": "GO",
                "pretrade_gate_passed": True,
                "pretrade_gate_failed_count": 0,
                "pretrade_gate_failed_checks": "",
                "failed_health_count": 0,
                "failed_health_checks": "",
                "total_asset": 1000000.0,
                "daily_return": 0.001,
                "drawdown": 0.0,
                "total_position_ratio": 0.3,
            }
        ]
    ).to_csv(history_path, index=False)
    pretrade_path.write_text(json.dumps({"status": "GO", "passed": True}), encoding="utf-8")
    paths = MonitorRefreshPaths(
        history=history_path,
        pretrade_gate=pretrade_path,
        status_json=tmp_path / "status.json",
        status_md=tmp_path / "status.md",
        alerts_json=tmp_path / "alerts.json",
        alerts_md=tmp_path / "alerts.md",
        metrics_prom=tmp_path / "metrics.prom",
        metrics_json=tmp_path / "metrics.json",
        grafana_dashboard=tmp_path / "dashboard.json",
        stability_json=tmp_path / "stability.json",
        stability_md=tmp_path / "stability.md",
        readiness_json=tmp_path / "readiness.json",
        readiness_md=tmp_path / "readiness.md",
    )

    result = refresh_monitoring(paths, target_days=20)

    assert result.level == "INFO"
    assert result.alerts_status == "OK"
    assert result.stability_status == "OBSERVING"
    assert result.readiness_status == "PAPER_READY"
    for output_path in result.written_paths.values():
        assert output_path
        assert pd.io.common.file_exists(output_path)
    assert json.loads(paths.readiness_json.read_text(encoding="utf-8"))["paper_ready"]
    assert "quant_monitor_level" in paths.metrics_prom.read_text(encoding="utf-8")


def test_refresh_monitoring_can_skip_dashboard(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    pretrade_path = tmp_path / "pretrade_gate.json"
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "data_quality_level": "INFO",
                "reconciliation_diff_count": 0,
                "risk_guard_status": "OK",
                "risk_guard_rejected_orders": 0,
                "pretrade_gate_status": "GO",
                "pretrade_gate_failed_count": 0,
                "failed_health_count": 0,
            }
        ]
    ).to_csv(history_path, index=False)
    pretrade_path.write_text(json.dumps({"status": "GO", "passed": True}), encoding="utf-8")
    paths = MonitorRefreshPaths(
        history=history_path,
        pretrade_gate=pretrade_path,
        status_json=tmp_path / "status.json",
        status_md=tmp_path / "status.md",
        alerts_json=tmp_path / "alerts.json",
        alerts_md=tmp_path / "alerts.md",
        metrics_prom=tmp_path / "metrics.prom",
        metrics_json=tmp_path / "metrics.json",
        grafana_dashboard=tmp_path / "dashboard.json",
        stability_json=tmp_path / "stability.json",
        stability_md=tmp_path / "stability.md",
        readiness_json=tmp_path / "readiness.json",
        readiness_md=tmp_path / "readiness.md",
    )

    result = refresh_monitoring(paths, write_dashboard=False)

    assert "grafana_dashboard" not in result.written_paths
    assert not paths.grafana_dashboard.exists()
