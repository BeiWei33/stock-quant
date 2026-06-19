from __future__ import annotations

import csv
import json

from quant.core.execution.audit import read_execution_audit_events
from quant.core.execution.refresh import ExecutionRefreshPaths, refresh_execution


def test_execution_refresh_preserves_existing_manual_fill_template(tmp_path) -> None:
    paths = _write_refresh_inputs(tmp_path, include_manual_package=True)
    original = paths.manual_fill_template.read_text(encoding="utf-8")

    result = refresh_execution(paths)

    assert result.status == "BLOCKED"
    assert result.authorization_status == "GO"
    assert result.broker_adapter_contract_status == "OK"
    assert result.manual_package_status == "READY"
    assert result.manual_validation_status == "ERROR"
    assert result.manual_reconciliation_status == "SKIPPED"
    assert result.audit_report_status == "BLOCKED"
    assert result.dashboard_status == "BLOCKED"
    assert paths.manual_fill_template.read_text(encoding="utf-8") == original
    assert paths.audit_report_json.exists()
    assert paths.audit_report_md.exists()
    assert paths.dashboard_html.exists()
    assert json.loads(paths.audit_report_json.read_text(encoding="utf-8"))["step_count"] == 7
    skipped = json.loads(paths.manual_reconciliation_json.read_text(encoding="utf-8"))
    assert skipped["status"] == "SKIPPED"
    events = read_execution_audit_events(paths.audit_log)
    assert [event.event_type for event in events] == [
        "execution_authorization",
        "broker_adapter_contract",
        "manual_package_existing",
        "manual_fill_validation",
        "manual_reconciliation",
        "execution_day_end",
        "config_health",
    ]


def test_execution_refresh_can_rebuild_manual_package(tmp_path) -> None:
    paths = _write_refresh_inputs(tmp_path, include_manual_package=False)

    result = refresh_execution(paths, rebuild_manual_package=True)

    assert result.manual_package_status == "READY"
    assert paths.manual_execution_json.exists()
    assert paths.manual_order_ticket.exists()
    assert paths.manual_fill_template.exists()
    ticket_rows = _read_csv(paths.manual_order_ticket)
    assert ticket_rows[0]["broker_order_id"] == "DRYRUN:order-1"
    events = read_execution_audit_events(paths.audit_log)
    assert any(event.event_type == "manual_package" for event in events)


def _write_refresh_inputs(tmp_path, *, include_manual_package: bool) -> ExecutionRefreshPaths:
    paths = ExecutionRefreshPaths(
        paper_plan=tmp_path / "paper_plan.json",
        risk_guard=tmp_path / "risk_guard.json",
        broker_submission=tmp_path / "broker_submission.json",
        execution_policy=tmp_path / "execution_policy.json",
        execution_authorization_json=tmp_path / "execution_authorization.json",
        execution_authorization_md=tmp_path / "execution_authorization.md",
        broker_adapter_contract_json=tmp_path / "broker_adapter_contract.json",
        broker_adapter_contract_md=tmp_path / "broker_adapter_contract.md",
        manual_execution_json=tmp_path / "manual_execution.json",
        manual_execution_md=tmp_path / "manual_execution.md",
        manual_order_ticket=tmp_path / "manual_order_ticket.csv",
        manual_fill_template=tmp_path / "manual_fill_template.csv",
        pretrade_gate=tmp_path / "pretrade_gate.json",
        manual_fill_validation_json=tmp_path / "manual_fill_validation.json",
        manual_fill_validation_md=tmp_path / "manual_fill_validation.md",
        manual_reconciliation_json=tmp_path / "manual_reconciliation.json",
        manual_reconciliation_md=tmp_path / "manual_reconciliation.md",
        manual_work_dir=tmp_path,
        paper_sqlite=tmp_path / "paper.sqlite3",
        execution_day_end_json=tmp_path / "execution_day_end.json",
        execution_day_end_md=tmp_path / "execution_day_end.md",
        monitor_status=tmp_path / "status_summary.json",
        readiness=tmp_path / "readiness.json",
        stocks=tmp_path / "stocks.csv",
        bars=tmp_path / "daily_bar.cleaned.csv",
        daily_config=tmp_path / "daily.yaml",
        cleaning_config=tmp_path / "cleaning.yaml",
        risk_guard_control=tmp_path / "risk_guard_control.env",
        monitor_history=tmp_path / "daily_history.csv",
        config_health_json=tmp_path / "config_health.json",
        config_health_md=tmp_path / "config_health.md",
        audit_log=tmp_path / "execution_audit.jsonl",
        audit_report_json=tmp_path / "execution_audit_report.json",
        audit_report_md=tmp_path / "execution_audit_report.md",
        dashboard_html=tmp_path / "execution_dashboard.html",
    )
    _write_json(
        paths.paper_plan,
        {
            "trade_date": "2024-09-09",
            "strategy": {"strategy_id": "momentum_rank"},
            "order_intents": [{"quantity": 100, "price": 10.5}],
        },
    )
    _write_json(paths.risk_guard, {"allowed": True, "accepted_orders": 1, "rejected_orders": 0})
    _write_json(
        paths.broker_submission,
        {
            "mode": "DRY_RUN",
            "adapter": "dry_run",
            "trade_date": "2024-09-09",
            "strategy_id": "momentum_rank",
            "risk_guard_allowed": True,
            "order_count": 1,
            "orders": [
                {
                    "broker_order_id": "DRYRUN:order-1",
                    "order_id": "order-1",
                    "account_id": "paper",
                    "strategy_id": "momentum_rank",
                    "ts_code": "000001.SZ",
                    "side": "BUY",
                    "quantity": 100,
                    "price": 10.5,
                    "target_weight": 0.05,
                    "trade_date": "2024-09-09",
                }
            ],
        },
    )
    _write_json(paths.execution_policy, {"allowed_modes": ["DRY_RUN"], "allowed_adapters": ["dry_run"]})
    _write_json(paths.pretrade_gate, {"status": "GO", "passed": True, "checks": []})
    _write_json(paths.monitor_status, {"level": "INFO", "latest_trade_date": "2024-09-09"})
    _write_json(paths.readiness, {"status": "PAPER_READY", "paper_ready": True, "live_ready": False})
    paths.daily_config.write_text("workflow: daily\n", encoding="utf-8")
    paths.cleaning_config.write_text("cleaning: true\n", encoding="utf-8")
    paths.risk_guard_control.write_text(
        "trade_mode=NORMAL\nmax_order_amount=100000\nmax_single_weight=0.10\nmax_total_buy_weight=0.95\n",
        encoding="utf-8",
    )
    _write_csv(paths.stocks, ["ts_code", "name", "exchange"], [["000001.SZ", "Ping An", "SZSE"]])
    _write_csv(
        paths.bars,
        ["ts_code", "trade_date", "open", "high", "low", "close", "volume", "amount"],
        [["000001.SZ", "2024-09-09", "10", "11", "9", "10.5", "1000", "10500"]],
    )
    _write_csv(paths.monitor_history, ["trade_date", "run_id", "run_status", "ok"], [["2024-09-09", "run-1", "OK", "true"]])
    if include_manual_package:
        _write_json(
            paths.manual_execution_json,
            {
                "status": "READY",
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "order_count": 1,
                "estimated_notional": 1050.0,
            },
        )
        paths.manual_execution_md.write_text("# Manual Execution Package\n", encoding="utf-8")
        _write_csv(
            paths.manual_order_ticket,
            [
                "trade_date",
                "ts_code",
                "side",
                "quantity",
                "limit_price",
                "estimated_notional",
                "account_id",
                "strategy_id",
                "order_id",
                "broker_order_id",
                "manual_status",
                "submitted_quantity",
                "submitted_price",
                "operator_note",
            ],
            [["2024-09-09", "000001.SZ", "BUY", "100", "10.5", "1050", "paper", "momentum_rank", "order-1", "DRYRUN:order-1", "PENDING", "", "", ""]],
        )
        _write_csv(
            paths.manual_fill_template,
            ["trade_date", "ts_code", "side", "quantity", "price", "amount", "broker_order_id", "order_id", "status", "operator_note"],
            [["2024-09-09", "000001.SZ", "BUY", "", "", "", "DRYRUN:order-1", "order-1", "", "keep-this-note"]],
        )
    return paths


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path, headers, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
