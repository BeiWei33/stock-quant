from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionArtifactStatus:
    name: str
    path: str
    status: str
    passed: bool | None
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionDayEndReport:
    status: str
    trade_date: str
    strategy_id: str
    order_count: int
    estimated_notional: float
    artifacts: list[ExecutionArtifactStatus]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "trade_date": self.trade_date,
            "strategy_id": self.strategy_id,
            "order_count": self.order_count,
            "estimated_notional": self.estimated_notional,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


@dataclass(frozen=True)
class ExecutionReportPaths:
    paper_plan: Path = Path("research_store/reports/paper_plan.json")
    risk_guard: Path = Path("research_store/reports/risk_guard.json")
    broker_submission: Path = Path("research_store/reports/broker_submission.json")
    execution_authorization: Path = Path("research_store/reports/execution_authorization.json")
    broker_adapter_contract: Path = Path("research_store/reports/broker_adapter_contract.json")
    manual_execution: Path = Path("research_store/reports/manual_execution.json")
    pretrade_gate: Path = Path("research_store/reports/pretrade_gate.json")
    manual_fill_validation: Path = Path("research_store/reports/manual_fill_validation.json")
    manual_reconciliation: Path = Path("research_store/reports/manual_reconciliation.json")
    monitor_status: Path = Path("research_store/monitoring/status_summary.json")
    readiness: Path = Path("research_store/monitoring/readiness.json")


def build_execution_day_end_report(paths: ExecutionReportPaths) -> ExecutionDayEndReport:
    paper_plan = _read_optional(paths.paper_plan)
    broker = _read_optional(paths.broker_submission)
    manual = _read_optional(paths.manual_execution)
    artifacts = [
        _paper_plan_status(paths.paper_plan, paper_plan),
        _risk_guard_status(paths.risk_guard, _read_optional(paths.risk_guard)),
        _broker_submission_status(paths.broker_submission, broker),
        _authorization_status(paths.execution_authorization, _read_optional(paths.execution_authorization)),
        _broker_adapter_contract_status(paths.broker_adapter_contract, _read_optional(paths.broker_adapter_contract)),
        _manual_execution_status(paths.manual_execution, manual),
        _pretrade_status(paths.pretrade_gate, _read_optional(paths.pretrade_gate)),
        _manual_validation_status(paths.manual_fill_validation, _read_optional(paths.manual_fill_validation)),
        _manual_reconciliation_status(paths.manual_reconciliation, _read_optional(paths.manual_reconciliation)),
        _monitor_status(paths.monitor_status, _read_optional(paths.monitor_status)),
        _readiness_status(paths.readiness, _read_optional(paths.readiness)),
    ]
    hard_failures = [
        artifact for artifact in artifacts
        if artifact.status in {"ERROR", "BLOCK", "REJECTED", "CRITICAL", "FAILED"}
    ]
    missing_required = [
        artifact for artifact in artifacts
        if artifact.status == "MISSING"
        and artifact.name
        in {
            "paper_plan",
            "risk_guard",
            "broker_submission",
            "execution_authorization",
            "broker_adapter_contract",
            "manual_execution",
            "pretrade_gate",
            "monitor_status",
            "readiness",
        }
    ]
    pending = [
        artifact for artifact in artifacts
        if artifact.status in {"PENDING", "MISSING", "SKIPPED"}
        and artifact.name in {"manual_fill_validation", "manual_reconciliation"}
    ]
    status = "BLOCKED" if hard_failures or missing_required else "PENDING_MANUAL" if pending else "READY"
    return ExecutionDayEndReport(
        status=status,
        trade_date=_trade_date(paper_plan, broker, manual),
        strategy_id=_strategy_id(paper_plan, broker, manual),
        order_count=_order_count(paper_plan, broker, manual),
        estimated_notional=_estimated_notional(broker, manual),
        artifacts=artifacts,
    )


def write_execution_day_end_json(report: ExecutionDayEndReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_execution_day_end_markdown(report: ExecutionDayEndReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_execution_day_end_markdown(report), encoding="utf-8")
    return path


def render_execution_day_end_markdown(report: ExecutionDayEndReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Trade Date", report.trade_date or "-"],
        ["Strategy", report.strategy_id or "-"],
        ["Orders", report.order_count],
        ["Estimated Notional", f"{report.estimated_notional:,.2f}"],
    ]
    artifact_rows = [
        [
            artifact.name,
            artifact.status,
            "-" if artifact.passed is None else artifact.passed,
            artifact.detail or "-",
            artifact.path,
        ]
        for artifact in report.artifacts
    ]
    return "\n".join(
        [
            f"# Execution Day-End Report - {report.trade_date or 'UNKNOWN'}",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Artifacts",
            _table(["Artifact", "Status", "Passed", "Detail", "Path"], artifact_rows),
            "",
        ]
    )


def _paper_plan_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("paper_plan", path)
    order_count = len(data.get("order_intents", [])) if isinstance(data.get("order_intents"), list) else 0
    return ExecutionArtifactStatus("paper_plan", str(path), "OK", True, f"orders={order_count}")


def _risk_guard_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("risk_guard", path)
    allowed = bool(data.get("allowed", False))
    rejected = int(data.get("rejected_orders", 0) or 0)
    status = "OK" if allowed and rejected == 0 else "REJECTED"
    return ExecutionArtifactStatus("risk_guard", str(path), status, allowed and rejected == 0, f"accepted={data.get('accepted_orders', 0)}, rejected={rejected}")


def _broker_submission_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("broker_submission", path)
    risk_allowed = bool(data.get("risk_guard_allowed", False))
    status = "OK" if risk_allowed else "BLOCK"
    return ExecutionArtifactStatus("broker_submission", str(path), status, risk_allowed, f"mode={data.get('mode', '-')}, orders={data.get('order_count', 0)}")


def _authorization_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("execution_authorization", path)
    passed = bool(data.get("passed", False))
    return ExecutionArtifactStatus("execution_authorization", str(path), "OK" if passed else "BLOCK", passed, f"mode={data.get('mode', '-')}, adapter={data.get('adapter', '-')}")


def _broker_adapter_contract_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("broker_adapter_contract", path)
    passed = bool(data.get("passed", False))
    status = str(data.get("status", "UNKNOWN")).upper()
    detail = f"adapter={data.get('adapter', '-')}, mode={data.get('mode', '-')}, submitted={bool(data.get('submitted', False))}"
    issue = str(data.get("issue", "") or "")
    if issue:
        detail = f"{detail}, issue={issue}"
    return ExecutionArtifactStatus("broker_adapter_contract", str(path), "OK" if passed and status == "OK" else "BLOCK", passed, detail)


def _manual_execution_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("manual_execution", path)
    status = str(data.get("status", "UNKNOWN")).upper()
    passed = status == "READY"
    return ExecutionArtifactStatus("manual_execution", str(path), status, passed, f"orders={data.get('order_count', 0)}, notional={float(data.get('estimated_notional', 0.0) or 0.0):,.2f}")


def _pretrade_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("pretrade_gate", path)
    passed = bool(data.get("passed", False))
    return ExecutionArtifactStatus("pretrade_gate", str(path), str(data.get("status", "UNKNOWN")).upper(), passed, f"checks={len(data.get('checks', [])) if isinstance(data.get('checks'), list) else 0}")


def _manual_validation_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return ExecutionArtifactStatus("manual_fill_validation", str(path), "PENDING", None, "manual fills not validated yet")
    passed = bool(data.get("passed", False))
    return ExecutionArtifactStatus("manual_fill_validation", str(path), "OK" if passed else "ERROR", passed, f"issues={len(data.get('issues', [])) if isinstance(data.get('issues'), list) else 0}")


def _manual_reconciliation_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return ExecutionArtifactStatus("manual_reconciliation", str(path), "PENDING", None, "manual reconciliation not run yet")
    reconciliation = data.get("reconciliation", {})
    if not isinstance(reconciliation, dict) and data.get("status"):
        status = str(data.get("status", "UNKNOWN")).upper()
        return ExecutionArtifactStatus("manual_reconciliation", str(path), status, None, str(data.get("detail", data.get("reason", "-"))))
    if isinstance(reconciliation, dict) and not reconciliation and data.get("status"):
        status = str(data.get("status", "UNKNOWN")).upper()
        return ExecutionArtifactStatus("manual_reconciliation", str(path), status, None, str(data.get("detail", data.get("reason", "-"))))
    status = str(reconciliation.get("status", "UNKNOWN")).upper() if isinstance(reconciliation, dict) else "UNKNOWN"
    return ExecutionArtifactStatus("manual_reconciliation", str(path), status, status == "OK", f"report_id={reconciliation.get('report_id', '-') if isinstance(reconciliation, dict) else '-'}")


def _monitor_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("monitor_status", path)
    level = str(data.get("level", "UNKNOWN")).upper()
    return ExecutionArtifactStatus("monitor_status", str(path), level, level == "INFO", f"latest={data.get('latest_trade_date', '-')}")


def _readiness_status(path: Path, data: dict[str, Any]) -> ExecutionArtifactStatus:
    if not data:
        return _missing("readiness", path)
    paper_ready = bool(data.get("paper_ready", False))
    live_ready = bool(data.get("live_ready", False))
    return ExecutionArtifactStatus("readiness", str(path), str(data.get("status", "UNKNOWN")).upper(), paper_ready, f"paper_ready={paper_ready}, live_ready={live_ready}")


def _missing(name: str, path: Path) -> ExecutionArtifactStatus:
    return ExecutionArtifactStatus(name, str(path), "MISSING", None, "artifact not found")


def _read_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _trade_date(*items: dict[str, Any]) -> str:
    for item in items:
        value = item.get("trade_date")
        if value:
            return str(value)
    return ""


def _strategy_id(*items: dict[str, Any]) -> str:
    for item in items:
        value = item.get("strategy_id")
        if value:
            return str(value)
        strategy = item.get("strategy")
        if isinstance(strategy, dict) and strategy.get("strategy_id"):
            return str(strategy["strategy_id"])
    return ""


def _order_count(*items: dict[str, Any]) -> int:
    for item in items:
        value = item.get("order_count")
        if value is not None:
            return int(value or 0)
        orders = item.get("order_intents") or item.get("orders")
        if isinstance(orders, list):
            return len(orders)
    return 0


def _estimated_notional(*items: dict[str, Any]) -> float:
    for item in items:
        value = item.get("estimated_notional")
        if value is not None:
            return float(value or 0.0)
        orders = item.get("orders")
        if isinstance(orders, list):
            return sum(
                abs(float(order.get("quantity", 0) or 0) * float(order.get("price", order.get("limit_price", 0.0)) or 0.0))
                for order in orders
                if isinstance(order, dict)
            )
    return 0.0


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
