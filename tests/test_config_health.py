from __future__ import annotations

import json

import pandas as pd

from quant.core.monitoring.config_health import (
    ConfigHealthPaths,
    build_config_health_report,
    render_config_health_markdown,
    write_config_health_json,
    write_config_health_markdown,
)


def test_config_health_reports_warning_for_pending_manual_validation(tmp_path) -> None:
    paths = _write_ok_files(tmp_path)
    paths.manual_fill_validation.write_text(
        json.dumps({"status": "ERROR", "passed": False, "issues": [{"field": "status"}]}),
        encoding="utf-8",
    )

    report = build_config_health_report(paths)

    assert report.status == "WARNING"
    assert report.error_count == 0
    assert report.warning_count >= 1
    assert any(check.name == "manual_fill_validation" and check.severity == "WARNING" for check in report.checks)
    assert any(check.name == "monitor_status" and check.status == "INFO" and check.passed for check in report.checks)
    assert "Config Health Report" in render_config_health_markdown(report)


def test_config_health_reports_error_for_missing_required_csv_column(tmp_path) -> None:
    paths = _write_ok_files(tmp_path)
    pd.DataFrame([{"ts_code": "000001.SZ"}]).to_csv(paths.stocks, index=False)

    report = build_config_health_report(paths)

    assert report.status == "ERROR"
    assert report.error_count >= 1
    assert any(check.name == "stocks" and check.status == "SCHEMA_ERROR" for check in report.checks)


def test_config_health_writers_emit_json_and_markdown(tmp_path) -> None:
    paths = _write_ok_files(tmp_path)
    report = build_config_health_report(paths)

    json_path = write_config_health_json(report, tmp_path / "config_health.json")
    markdown_path = write_config_health_markdown(report, tmp_path / "config_health.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "OK"
    assert "risk_guard_control" in markdown_path.read_text(encoding="utf-8")


def _write_ok_files(tmp_path) -> ConfigHealthPaths:
    paths = ConfigHealthPaths(
        stocks=tmp_path / "stocks.csv",
        bars=tmp_path / "daily_bar.cleaned.csv",
        daily_config=tmp_path / "daily.yaml",
        cleaning_config=tmp_path / "cleaning.yaml",
        risk_guard_control=tmp_path / "risk_guard_control.env",
        execution_policy=tmp_path / "execution_policy.json",
        broker_submission=tmp_path / "broker_submission.json",
        execution_authorization=tmp_path / "execution_authorization.json",
        broker_adapter_contract=tmp_path / "broker_adapter_contract.json",
        pretrade_gate=tmp_path / "pretrade_gate.json",
        manual_order_ticket=tmp_path / "manual_order_ticket.csv",
        manual_fill_template=tmp_path / "manual_fill_template.csv",
        manual_fill_validation=tmp_path / "manual_fill_validation.json",
        execution_day_end=tmp_path / "execution_day_end.json",
        monitor_status=tmp_path / "status_summary.json",
        readiness=tmp_path / "readiness.json",
        history=tmp_path / "daily_history.csv",
    )
    pd.DataFrame([{"ts_code": "000001.SZ", "name": "A", "exchange": "SZ"}]).to_csv(paths.stocks, index=False)
    pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "2024-09-09",
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.0,
                "volume": 1000,
                "amount": 10000.0,
            }
        ]
    ).to_csv(paths.bars, index=False)
    paths.daily_config.write_text("source:\n  type: csv\n", encoding="utf-8")
    paths.cleaning_config.write_text("ohlc:\n  enabled: true\n", encoding="utf-8")
    paths.risk_guard_control.write_text(
        "\n".join(
            [
                "trade_mode=NORMAL",
                "max_order_amount=100000",
                "max_single_weight=0.1",
                "max_total_buy_weight=0.95",
            ]
        ),
        encoding="utf-8",
    )
    paths.execution_policy.write_text(
        json.dumps({"allowed_modes": ["DRY_RUN"], "allowed_adapters": ["dry_run"]}),
        encoding="utf-8",
    )
    paths.broker_submission.write_text(
        json.dumps(
            {
                "mode": "DRY_RUN",
                "adapter": "dry_run",
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "order_count": 1,
                "orders": [],
            }
        ),
        encoding="utf-8",
    )
    paths.execution_authorization.write_text(json.dumps({"status": "GO"}), encoding="utf-8")
    paths.broker_adapter_contract.write_text(
        json.dumps({"status": "OK", "passed": True, "adapter": "dry_run", "mode": "DRY_RUN", "submitted": False}),
        encoding="utf-8",
    )
    paths.pretrade_gate.write_text(json.dumps({"status": "GO"}), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "quantity": 100,
                "limit_price": 10.0,
                "order_id": "order-1",
                "broker_order_id": "DRYRUN:order-1",
            }
        ]
    ).to_csv(paths.manual_order_ticket, index=False)
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "quantity": 100,
                "price": 10.0,
                "amount": 1000.0,
                "order_id": "order-1",
                "broker_order_id": "DRYRUN:order-1",
                "status": "FILLED",
            }
        ]
    ).to_csv(paths.manual_fill_template, index=False)
    paths.manual_fill_validation.write_text(json.dumps({"status": "OK", "passed": True}), encoding="utf-8")
    paths.execution_day_end.write_text(json.dumps({"status": "READY"}), encoding="utf-8")
    paths.monitor_status.write_text(json.dumps({"level": "INFO"}), encoding="utf-8")
    paths.readiness.write_text(json.dumps({"status": "PAPER_READY"}), encoding="utf-8")
    pd.DataFrame([{"trade_date": "2024-09-09", "run_id": "run-1", "run_status": "SUCCESS", "ok": True}]).to_csv(paths.history, index=False)
    return paths
