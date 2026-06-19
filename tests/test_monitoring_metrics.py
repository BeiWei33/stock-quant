from __future__ import annotations

import json

import pandas as pd

from quant.core.monitoring.metrics import (
    build_monitor_metrics,
    grafana_dashboard,
    render_prometheus_metrics,
    write_grafana_dashboard,
    write_metrics_json,
    write_prometheus_metrics,
)


def test_build_monitor_metrics_exports_status_and_history(tmp_path) -> None:
    status_path = tmp_path / "status_summary.json"
    history_path = tmp_path / "daily_history.csv"
    status_path.write_text(
        json.dumps(
            {
                "latest_trade_date": "2024-09-09",
                "latest_run_id": "run-1",
                "level": "CRITICAL",
                "latest_ok": False,
                "success_rate": 0.5,
                "total_runs": 2,
                "consecutive_unhealthy_runs": 2,
                "latest_total_asset": 999000.0,
                "latest_daily_return": -0.01,
                "latest_drawdown": -0.02,
                "max_drawdown": -0.03,
                "latest_position_ratio": 0.3,
                "total_orders": 3,
                "total_rejected_orders": 1,
                "data_quality_issue_count": 2,
                "reconciliation_diff_count": 0,
                "risk_guard_rejected_runs": 1,
                "risk_guard_rejected_orders": 1,
                "latest_pretrade_gate_status": "BLOCK",
                "latest_pretrade_gate_passed": False,
                "pretrade_gate_block_runs": 1,
                "failed_health_count": 1,
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame([{"trade_date": "2024-09-06"}, {"trade_date": "2024-09-09"}]).to_csv(
        history_path,
        index=False,
    )

    samples = build_monitor_metrics(status_path, history_path)
    by_name = {sample.name: sample for sample in samples}

    assert by_name["quant_monitor_level"].value == 2.0
    assert by_name["quant_monitor_level"].labels["level"] == "CRITICAL"
    assert by_name["quant_monitor_pretrade_gate_passed"].value == 0.0
    assert by_name["quant_monitor_pretrade_gate_passed"].labels["status"] == "BLOCK"
    assert by_name["quant_monitor_history_rows"].value == 2.0


def test_render_prometheus_metrics_escapes_labels(tmp_path) -> None:
    status_path = tmp_path / "status_summary.json"
    status_path.write_text(
        json.dumps(
            {
                "latest_trade_date": "2024-09-09",
                "latest_run_id": 'run"1',
                "level": "INFO",
                "latest_ok": True,
            }
        ),
        encoding="utf-8",
    )

    text = render_prometheus_metrics(build_monitor_metrics(status_path))

    assert "# HELP quant_monitor_level" in text
    assert 'run_id="run\\"1"' in text
    assert "quant_monitor_level" in text


def test_metrics_writers_and_dashboard_template(tmp_path) -> None:
    status_path = tmp_path / "status_summary.json"
    status_path.write_text(
        json.dumps(
            {
                "latest_trade_date": "2024-09-09",
                "latest_run_id": "run-1",
                "level": "WARNING",
                "latest_ok": False,
            }
        ),
        encoding="utf-8",
    )
    samples = build_monitor_metrics(status_path)

    prom_path = write_prometheus_metrics(samples, tmp_path / "metrics.prom")
    json_path = write_metrics_json(samples, tmp_path / "metrics.json")
    dashboard_path = write_grafana_dashboard(tmp_path / "grafana_dashboard.json")

    assert "quant_monitor_level" in prom_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["metrics"][0]["name"]
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert dashboard["title"] == "Personal Quant Monitor"
    assert grafana_dashboard()["panels"][0]["targets"][0]["expr"] == "quant_monitor_level"
