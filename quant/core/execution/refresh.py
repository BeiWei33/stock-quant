from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from quant.core.execution.adapters import (
    DryRunBrokerAdapter,
    QmtBrokerAdapterSkeleton,
    build_broker_adapter_contract_report,
    write_broker_adapter_contract_json,
    write_broker_adapter_contract_markdown,
)
from quant.core.execution.audit import (
    append_execution_audit,
    build_execution_audit_report,
    read_execution_audit_events,
    write_execution_audit_report_json,
    write_execution_audit_report_markdown,
)
from quant.core.execution.authorization import (
    build_execution_authorization_report,
    write_execution_authorization_json,
    write_execution_authorization_markdown,
)
from quant.core.execution.manual import (
    build_manual_execution_package,
    write_manual_execution_json,
    write_manual_execution_markdown,
)
from quant.core.execution.manual_reconcile import (
    build_manual_reconciliation,
    validate_manual_fills,
    write_manual_reconciliation_json,
    write_manual_reconciliation_markdown,
    write_manual_validation_json,
    write_manual_validation_markdown,
)
from quant.core.monitoring.config_health import (
    ConfigHealthPaths,
    build_config_health_report,
    write_config_health_json,
    write_config_health_markdown,
)
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.reporting.execution_dashboard import (
    ExecutionDashboardPaths,
    build_execution_dashboard,
    write_execution_dashboard_html,
)
from quant.core.reporting.execution_report import (
    ExecutionReportPaths,
    build_execution_day_end_report,
    write_execution_day_end_json,
    write_execution_day_end_markdown,
)


@dataclass(frozen=True)
class ExecutionRefreshPaths:
    paper_plan: Path = Path("research_store/reports/paper_plan.json")
    risk_guard: Path = Path("research_store/reports/risk_guard.json")
    broker_submission: Path = Path("research_store/reports/broker_submission.json")
    execution_policy: Path = Path("config/execution_policy.generated.json")
    execution_authorization_json: Path = Path("research_store/reports/execution_authorization.json")
    execution_authorization_md: Path = Path("research_store/reports/execution_authorization.md")
    broker_adapter_contract_json: Path = Path("research_store/reports/broker_adapter_contract.json")
    broker_adapter_contract_md: Path = Path("research_store/reports/broker_adapter_contract.md")
    manual_execution_json: Path = Path("research_store/reports/manual_execution.json")
    manual_execution_md: Path = Path("research_store/reports/manual_execution.md")
    manual_order_ticket: Path = Path("research_store/reports/manual_order_ticket.csv")
    manual_fill_template: Path = Path("research_store/reports/manual_fill_template.csv")
    pretrade_gate: Path = Path("research_store/reports/pretrade_gate.json")
    manual_fill_validation_json: Path = Path("research_store/reports/manual_fill_validation.json")
    manual_fill_validation_md: Path = Path("research_store/reports/manual_fill_validation.md")
    manual_reconciliation_json: Path = Path("research_store/reports/manual_reconciliation.json")
    manual_reconciliation_md: Path = Path("research_store/reports/manual_reconciliation.md")
    manual_work_dir: Path = Path("research_store/reports")
    paper_sqlite: Path = Path("research_store/paper_trading.sqlite3")
    execution_day_end_json: Path = Path("research_store/reports/execution_day_end.json")
    execution_day_end_md: Path = Path("research_store/reports/execution_day_end.md")
    monitor_status: Path = Path("research_store/monitoring/status_summary.json")
    readiness: Path = Path("research_store/monitoring/readiness.json")
    stocks: Path = Path("research_store/sample/stocks.csv")
    bars: Path = Path("research_store/sample/daily_bar.cleaned.csv")
    daily_config: Path = Path("config/daily.yaml")
    cleaning_config: Path = Path("config/cleaning.yaml")
    risk_guard_control: Path = Path("research_store/state/risk_guard_control.env")
    monitor_history: Path = Path("research_store/monitoring/daily_history.csv")
    config_health_json: Path = Path("research_store/monitoring/config_health.json")
    config_health_md: Path = Path("research_store/monitoring/config_health.md")
    audit_log: Path = Path("research_store/reports/execution_audit.jsonl")
    audit_report_json: Path = Path("research_store/reports/execution_audit_report.json")
    audit_report_md: Path = Path("research_store/reports/execution_audit_report.md")
    dashboard_html: Path = Path("research_store/reports/execution_dashboard.html")


@dataclass(frozen=True)
class ExecutionRefreshResult:
    status: str
    authorization_status: str
    broker_adapter_contract_status: str
    manual_package_status: str
    manual_validation_status: str
    manual_reconciliation_status: str
    day_end_status: str
    config_health_status: str
    audit_report_status: str
    dashboard_status: str
    artifact_paths: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def refresh_execution(
    paths: ExecutionRefreshPaths = ExecutionRefreshPaths(),
    *,
    account_id: str = "paper",
    trade_date_override: str = "",
    amount_tolerance: float = 0.01,
    allow_incomplete: bool = False,
    rebuild_manual_package: bool = False,
    run_reconciliation: bool = True,
) -> ExecutionRefreshResult:
    authorization = build_execution_authorization_report(
        broker_submission_path=paths.broker_submission,
        policy_path=paths.execution_policy if paths.execution_policy.exists() else None,
    )
    authorization_json = write_execution_authorization_json(authorization, paths.execution_authorization_json)
    authorization_md = write_execution_authorization_markdown(authorization, paths.execution_authorization_md)
    append_execution_audit(
        event_type="execution_authorization",
        payload=authorization.to_dict(),
        path=paths.audit_log,
        artifact_paths={"json": authorization_json, "markdown": authorization_md, "policy": paths.execution_policy},
        summary={"failed_checks": [check.name for check in authorization.checks if not check.passed]},
    )

    broker_submission_payload = _read_object(paths.broker_submission)
    adapter_contract = build_broker_adapter_contract_report(
        adapter=_adapter_for_submission(broker_submission_payload),
        submission=broker_submission_payload,
        authorization=authorization,
    )
    adapter_contract_json = write_broker_adapter_contract_json(adapter_contract, paths.broker_adapter_contract_json)
    adapter_contract_md = write_broker_adapter_contract_markdown(adapter_contract, paths.broker_adapter_contract_md)
    append_execution_audit(
        event_type="broker_adapter_contract",
        payload=adapter_contract.to_dict(),
        path=paths.audit_log,
        artifact_paths={"json": adapter_contract_json, "markdown": adapter_contract_md},
        summary={"issue": adapter_contract.issue},
    )

    manual_package_status = "SKIPPED"
    if authorization.passed and adapter_contract.passed:
        manual_payload = _load_existing_manual_package(paths)
        if rebuild_manual_package or manual_payload is None:
            manual_package = build_manual_execution_package(
                broker_submission_path=paths.broker_submission,
                order_ticket_path=paths.manual_order_ticket,
                fill_template_path=paths.manual_fill_template,
            )
            manual_json = write_manual_execution_json(manual_package, paths.manual_execution_json)
            manual_md = write_manual_execution_markdown(manual_package, paths.manual_execution_md)
            manual_payload = manual_package.to_dict()
            manual_package_status = manual_package.status
            package_event_type = "manual_package"
        else:
            manual_json = paths.manual_execution_json
            manual_md = paths.manual_execution_md
            manual_package_status = str(manual_payload.get("status", "UNKNOWN")).upper()
            package_event_type = "manual_package_existing"
        append_execution_audit(
            event_type=package_event_type,
            payload=manual_payload,
            path=paths.audit_log,
            artifact_paths={
                "json": manual_json,
                "markdown": manual_md,
                "order_ticket": paths.manual_order_ticket,
                "fill_template": paths.manual_fill_template,
            },
            summary={"rebuild": bool(rebuild_manual_package)},
        )

    validation_status = "SKIPPED"
    validation_passed = False
    if authorization.passed and adapter_contract.passed and paths.manual_order_ticket.exists() and paths.manual_fill_template.exists():
        validation = validate_manual_fills(
            order_ticket_path=paths.manual_order_ticket,
            fill_template_path=paths.manual_fill_template,
            require_complete=not allow_incomplete,
            amount_tolerance=amount_tolerance,
        )
        validation_json = write_manual_validation_json(validation, paths.manual_fill_validation_json)
        validation_md = write_manual_validation_markdown(validation, paths.manual_fill_validation_md)
        validation_status = validation.status
        validation_passed = validation.passed
        append_execution_audit(
            event_type="manual_fill_validation",
            payload=validation.to_dict(),
            path=paths.audit_log,
            artifact_paths={
                "json": validation_json,
                "markdown": validation_md,
                "order_ticket": paths.manual_order_ticket,
                "fills": paths.manual_fill_template,
            },
            summary={"issue_count": len(validation.issues), "allow_incomplete": bool(allow_incomplete)},
        )

    reconciliation_status = "SKIPPED"
    if validation_passed and run_reconciliation:
        trade_date = _refresh_trade_date(trade_date_override, paths)
        bundle = build_manual_reconciliation(
            order_ticket_path=paths.manual_order_ticket,
            fill_template_path=paths.manual_fill_template,
            trade_date=trade_date,
            account_id=account_id,
            output_dir=paths.manual_work_dir,
            require_complete=not allow_incomplete,
            amount_tolerance=amount_tolerance,
        )
        store = SqliteStore(paths.paper_sqlite)
        store.init_schema()
        store.save_trade_reconciliation_report(bundle.reconciliation)
        reconciliation_json = write_manual_reconciliation_json(bundle, paths.manual_reconciliation_json)
        reconciliation_md = write_manual_reconciliation_markdown(bundle, paths.manual_reconciliation_md)
        reconciliation_status = bundle.reconciliation.status
        append_execution_audit(
            event_type="manual_reconciliation",
            payload=bundle.to_dict(),
            path=paths.audit_log,
            artifact_paths={
                "json": reconciliation_json,
                "markdown": reconciliation_md,
                "sqlite": paths.paper_sqlite,
                "local_orders": bundle.local_orders_path,
                "broker_orders": bundle.broker_orders_path,
                "broker_fills": bundle.broker_fills_path,
            },
            summary={"report_id": bundle.reconciliation.report_id},
        )
    else:
        reason = "manual validation did not pass" if not validation_passed else "reconciliation disabled"
        _write_skipped_reconciliation(paths.manual_reconciliation_json, paths.manual_reconciliation_md, reason)
        append_execution_audit(
            event_type="manual_reconciliation",
            payload={
                "status": "SKIPPED",
                "passed": None,
                "trade_date": _safe_trade_date(paths),
                "strategy_id": _safe_strategy_id(paths),
                "order_count": _safe_order_count(paths),
                "reason": reason,
            },
            path=paths.audit_log,
            artifact_paths={"json": paths.manual_reconciliation_json, "markdown": paths.manual_reconciliation_md},
            status="SKIPPED",
            passed=None,
            summary={"reason": reason},
        )

    day_end = build_execution_day_end_report(_execution_report_paths(paths))
    day_end_json = write_execution_day_end_json(day_end, paths.execution_day_end_json)
    day_end_md = write_execution_day_end_markdown(day_end, paths.execution_day_end_md)
    append_execution_audit(
        event_type="execution_day_end",
        payload=day_end.to_dict(),
        path=paths.audit_log,
        artifact_paths={"json": day_end_json, "markdown": day_end_md},
        passed=day_end.status == "READY",
        summary={
            "blocked_artifacts": [
                artifact.name
                for artifact in day_end.artifacts
                if artifact.status in {"ERROR", "BLOCK", "REJECTED", "CRITICAL", "FAILED"}
            ],
            "pending_artifacts": [
                artifact.name
                for artifact in day_end.artifacts
                if artifact.status in {"PENDING", "MISSING", "SKIPPED"}
            ],
        },
    )

    config_health = build_config_health_report(_config_health_paths(paths))
    config_json = write_config_health_json(config_health, paths.config_health_json)
    config_md = write_config_health_markdown(config_health, paths.config_health_md)
    append_execution_audit(
        event_type="config_health",
        payload=config_health.to_dict(),
        path=paths.audit_log,
        artifact_paths={"json": config_json, "markdown": config_md},
        passed=config_health.error_count == 0,
        summary={"errors": config_health.error_count, "warnings": config_health.warning_count},
    )

    audit_report = build_execution_audit_report(read_execution_audit_events(paths.audit_log))
    write_execution_audit_report_json(audit_report, paths.audit_report_json)
    write_execution_audit_report_markdown(audit_report, paths.audit_report_md)
    dashboard = build_execution_dashboard(
        ExecutionDashboardPaths(
            execution_day_end=paths.execution_day_end_json,
            config_health=paths.config_health_json,
            readiness=paths.readiness,
            audit_report=paths.audit_report_json,
        )
    )
    write_execution_dashboard_html(dashboard, paths.dashboard_html)

    return ExecutionRefreshResult(
        status=_refresh_status(authorization.status, day_end.status, config_health.status),
        authorization_status=authorization.status,
        broker_adapter_contract_status=adapter_contract.status,
        manual_package_status=manual_package_status,
        manual_validation_status=validation_status,
        manual_reconciliation_status=reconciliation_status,
        day_end_status=day_end.status,
        config_health_status=config_health.status,
        audit_report_status=audit_report.status,
        dashboard_status=dashboard.status,
        artifact_paths={
            "execution_authorization": str(paths.execution_authorization_json),
            "broker_adapter_contract": str(paths.broker_adapter_contract_json),
            "manual_execution": str(paths.manual_execution_json),
            "manual_fill_validation": str(paths.manual_fill_validation_json),
            "manual_reconciliation": str(paths.manual_reconciliation_json),
            "execution_day_end": str(paths.execution_day_end_json),
            "config_health": str(paths.config_health_json),
            "audit_log": str(paths.audit_log),
            "audit_report": str(paths.audit_report_json),
            "dashboard": str(paths.dashboard_html),
        },
    )


def _execution_report_paths(paths: ExecutionRefreshPaths) -> ExecutionReportPaths:
    return ExecutionReportPaths(
        paper_plan=paths.paper_plan,
        risk_guard=paths.risk_guard,
        broker_submission=paths.broker_submission,
        execution_authorization=paths.execution_authorization_json,
        broker_adapter_contract=paths.broker_adapter_contract_json,
        manual_execution=paths.manual_execution_json,
        pretrade_gate=paths.pretrade_gate,
        manual_fill_validation=paths.manual_fill_validation_json,
        manual_reconciliation=paths.manual_reconciliation_json,
        monitor_status=paths.monitor_status,
        readiness=paths.readiness,
    )


def _config_health_paths(paths: ExecutionRefreshPaths) -> ConfigHealthPaths:
    return ConfigHealthPaths(
        stocks=paths.stocks,
        bars=paths.bars,
        daily_config=paths.daily_config,
        cleaning_config=paths.cleaning_config,
        risk_guard_control=paths.risk_guard_control,
        execution_policy=paths.execution_policy,
        broker_submission=paths.broker_submission,
        execution_authorization=paths.execution_authorization_json,
        broker_adapter_contract=paths.broker_adapter_contract_json,
        pretrade_gate=paths.pretrade_gate,
        manual_order_ticket=paths.manual_order_ticket,
        manual_fill_template=paths.manual_fill_template,
        manual_fill_validation=paths.manual_fill_validation_json,
        execution_day_end=paths.execution_day_end_json,
        monitor_status=paths.monitor_status,
        readiness=paths.readiness,
        history=paths.monitor_history,
    )


def _load_existing_manual_package(paths: ExecutionRefreshPaths) -> dict[str, object] | None:
    if not (paths.manual_execution_json.exists() and paths.manual_order_ticket.exists() and paths.manual_fill_template.exists()):
        return None
    data = json.loads(paths.manual_execution_json.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _adapter_for_submission(submission: dict[str, object]):
    adapter = str(submission.get("adapter", ""))
    if adapter == "dry_run":
        return DryRunBrokerAdapter()
    if adapter == "qmt":
        return QmtBrokerAdapterSkeleton()
    raise ValueError(f"unsupported broker adapter: {adapter or 'UNKNOWN'}")


def _read_object(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _refresh_trade_date(override: str, paths: ExecutionRefreshPaths) -> date:
    if override:
        return date.fromisoformat(override)
    data = json.loads(paths.manual_execution_json.read_text(encoding="utf-8"))
    value = str(data.get("trade_date", "")) if isinstance(data, dict) else ""
    if not value:
        data = json.loads(paths.broker_submission.read_text(encoding="utf-8"))
        value = str(data.get("trade_date", "")) if isinstance(data, dict) else ""
    return date.fromisoformat(value)


def _write_skipped_reconciliation(json_path: Path, markdown_path: Path, reason: str) -> None:
    payload = {
        "status": "SKIPPED",
        "passed": None,
        "reason": reason,
        "reconciliation": {},
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        "\n".join(["# Manual Execution Reconciliation", "", f"Status: `SKIPPED`", f"Reason: {reason}", ""]),
        encoding="utf-8",
    )


def _safe_trade_date(paths: ExecutionRefreshPaths) -> str:
    try:
        data = _read_object(paths.broker_submission)
        return str(data.get("trade_date", ""))
    except Exception:
        return ""


def _safe_strategy_id(paths: ExecutionRefreshPaths) -> str:
    try:
        data = _read_object(paths.broker_submission)
        return str(data.get("strategy_id", ""))
    except Exception:
        return ""


def _safe_order_count(paths: ExecutionRefreshPaths) -> int:
    try:
        data = _read_object(paths.broker_submission)
        return int(data.get("order_count", 0) or 0)
    except Exception:
        return 0


def _refresh_status(authorization_status: str, day_end_status: str, config_status: str) -> str:
    if authorization_status != "GO" or day_end_status == "BLOCKED" or config_status == "ERROR":
        return "BLOCKED"
    if day_end_status == "PENDING_MANUAL" or config_status == "WARNING":
        return "PENDING_MANUAL"
    return "READY"
