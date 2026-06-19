from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ExecutionAuditEvent:
    event_id: str
    timestamp: str
    event_type: str
    status: str
    passed: bool | None
    trade_date: str
    strategy_id: str
    order_count: int
    notional: float
    artifact_paths: dict[str, str]
    summary: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionAuditStep:
    event_type: str
    status: str
    passed: bool | None
    timestamp: str
    trade_date: str
    strategy_id: str
    order_count: int
    notional: float
    detail: str
    artifact_paths: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionAuditReport:
    status: str
    trade_date: str
    strategy_id: str
    started_at: str
    ended_at: str
    step_count: int
    steps: list[ExecutionAuditStep]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "trade_date": self.trade_date,
            "strategy_id": self.strategy_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "step_count": self.step_count,
            "steps": [step.to_dict() for step in self.steps],
        }


def build_execution_audit_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    artifact_paths: dict[str, Path | str] | None = None,
    status: str | None = None,
    passed: bool | None = None,
    summary: dict[str, object] | None = None,
    timestamp: datetime | None = None,
) -> ExecutionAuditEvent:
    normalized_status = (status or _status(payload)).upper()
    return ExecutionAuditEvent(
        event_id=uuid4().hex,
        timestamp=(timestamp or datetime.now(UTC)).isoformat(),
        event_type=event_type,
        status=normalized_status,
        passed=_passed(payload, normalized_status, passed),
        trade_date=_trade_date(payload),
        strategy_id=_strategy_id(payload),
        order_count=_order_count(payload),
        notional=_notional(payload),
        artifact_paths={name: str(path) for name, path in (artifact_paths or {}).items()},
        summary=summary or {},
    )


def append_execution_audit_event(event: ExecutionAuditEvent, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
        file.write("\n")
    return path


def append_execution_audit(
    *,
    event_type: str,
    payload: dict[str, Any],
    path: Path,
    artifact_paths: dict[str, Path | str] | None = None,
    status: str | None = None,
    passed: bool | None = None,
    summary: dict[str, object] | None = None,
) -> Path:
    event = build_execution_audit_event(
        event_type=event_type,
        payload=payload,
        artifact_paths=artifact_paths,
        status=status,
        passed=passed,
        summary=summary,
    )
    return append_execution_audit_event(event, path)


def read_execution_audit_events(path: Path) -> list[ExecutionAuditEvent]:
    if not path.exists():
        return []
    events: list[ExecutionAuditEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        events.append(
            ExecutionAuditEvent(
                event_id=str(payload.get("event_id", "")),
                timestamp=str(payload.get("timestamp", "")),
                event_type=str(payload.get("event_type", "")),
                status=str(payload.get("status", "")),
                passed=payload.get("passed") if isinstance(payload.get("passed"), bool) else None,
                trade_date=str(payload.get("trade_date", "")),
                strategy_id=str(payload.get("strategy_id", "")),
                order_count=int(payload.get("order_count", 0) or 0),
                notional=float(payload.get("notional", 0.0) or 0.0),
                artifact_paths={
                    str(name): str(value)
                    for name, value in dict(payload.get("artifact_paths", {})).items()
                },
                summary=dict(payload.get("summary", {})),
            )
        )
    return events


def build_execution_audit_report(events: list[ExecutionAuditEvent]) -> ExecutionAuditReport:
    cycle = _latest_cycle(events)
    latest_by_type = _latest_by_type(cycle)
    steps = [
        _step_from_event(event_type, latest_by_type.get(event_type))
        for event_type in _expected_event_types()
    ]
    present_steps = [step for step in steps if step.status != "MISSING"]
    hard_failures = [
        step for step in present_steps
        if step.passed is False or step.status in {"ERROR", "BLOCK", "BLOCKED", "FAILED", "REJECTED"}
    ]
    incomplete = [step for step in steps if step.status in {"MISSING", "SKIPPED"} or step.passed is None]
    warnings = [step for step in present_steps if step.status == "WARNING"]
    status = "BLOCKED" if hard_failures else "INCOMPLETE" if incomplete else "WARNING" if warnings else "OK"
    return ExecutionAuditReport(
        status=status,
        trade_date=_first_non_empty(step.trade_date for step in steps),
        strategy_id=_first_non_empty(step.strategy_id for step in steps),
        started_at=cycle[0].timestamp if cycle else "",
        ended_at=cycle[-1].timestamp if cycle else "",
        step_count=len(present_steps),
        steps=steps,
    )


def write_execution_audit_report_json(report: ExecutionAuditReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_execution_audit_report_markdown(report: ExecutionAuditReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_execution_audit_report_markdown(report), encoding="utf-8")
    return path


def render_execution_audit_report_markdown(report: ExecutionAuditReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Trade Date", report.trade_date or "-"],
        ["Strategy", report.strategy_id or "-"],
        ["Started At", report.started_at or "-"],
        ["Ended At", report.ended_at or "-"],
        ["Steps", report.step_count],
    ]
    step_rows = [
        [
            step.event_type,
            step.status,
            "-" if step.passed is None else step.passed,
            step.trade_date or "-",
            step.strategy_id or "-",
            step.detail or "-",
            _artifact_summary(step.artifact_paths),
        ]
        for step in report.steps
    ]
    return "\n".join(
        [
            "# Execution Audit Report",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Latest Refresh Cycle",
            _table(["Step", "Status", "Passed", "Trade Date", "Strategy", "Detail", "Artifacts"], step_rows),
            "",
        ]
    )


def _status(payload: dict[str, Any]) -> str:
    direct = payload.get("status")
    if direct:
        return str(direct)
    reconciliation = payload.get("reconciliation")
    if isinstance(reconciliation, dict) and reconciliation.get("status"):
        return str(reconciliation["status"])
    validation = payload.get("validation")
    if isinstance(validation, dict) and validation.get("status"):
        return str(validation["status"])
    return "UNKNOWN"


def _passed(payload: dict[str, Any], status: str, override: bool | None) -> bool | None:
    if override is not None:
        return override
    direct = payload.get("passed")
    if isinstance(direct, bool):
        return direct
    validation = payload.get("validation")
    if isinstance(validation, dict) and isinstance(validation.get("passed"), bool):
        return bool(validation["passed"])
    if status in {"GO", "OK", "READY"}:
        return True
    if status in {"BLOCK", "BLOCKED", "ERROR", "FAILED", "REJECTED", "DIFF"}:
        return False
    return None


def _trade_date(payload: dict[str, Any]) -> str:
    for container in (payload, payload.get("reconciliation"), payload.get("validation")):
        if isinstance(container, dict) and container.get("trade_date"):
            return str(container["trade_date"])
    return ""


def _strategy_id(payload: dict[str, Any]) -> str:
    value = payload.get("strategy_id")
    if value:
        return str(value)
    strategy = payload.get("strategy")
    if isinstance(strategy, dict) and strategy.get("strategy_id"):
        return str(strategy["strategy_id"])
    return ""


def _order_count(payload: dict[str, Any]) -> int:
    for container in (payload, payload.get("validation"), payload.get("reconciliation")):
        if not isinstance(container, dict):
            continue
        if container.get("order_count") is not None:
            return int(container.get("order_count") or 0)
        if container.get("broker_order_count") is not None:
            return int(container.get("broker_order_count") or 0)
    orders = payload.get("orders") or payload.get("order_intents")
    return len(orders) if isinstance(orders, list) else 0


def _notional(payload: dict[str, Any]) -> float:
    for key in ("notional", "estimated_notional", "total_fill_amount"):
        if payload.get(key) is not None:
            return float(payload.get(key) or 0.0)
    validation = payload.get("validation")
    if isinstance(validation, dict) and validation.get("total_fill_amount") is not None:
        return float(validation.get("total_fill_amount") or 0.0)
    orders = payload.get("orders") or payload.get("order_intents")
    if isinstance(orders, list):
        total = 0.0
        for order in orders:
            if not isinstance(order, dict):
                continue
            total += abs(float(order.get("quantity", 0) or 0) * float(order.get("price", order.get("limit_price", 0.0)) or 0.0))
        return total
    return 0.0


def _latest_cycle(events: list[ExecutionAuditEvent]) -> list[ExecutionAuditEvent]:
    if not events:
        return []
    start = 0
    for index in range(len(events) - 1, -1, -1):
        if events[index].event_type == "execution_authorization":
            start = index
            break
    return events[start:]


def _latest_by_type(events: list[ExecutionAuditEvent]) -> dict[str, ExecutionAuditEvent]:
    latest: dict[str, ExecutionAuditEvent] = {}
    for event in events:
        key = "manual_package" if event.event_type == "manual_package_existing" else event.event_type
        latest[key] = event
    return latest


def _expected_event_types() -> list[str]:
    return [
        "execution_authorization",
        "broker_adapter_contract",
        "manual_package",
        "manual_fill_validation",
        "manual_reconciliation",
        "execution_day_end",
        "config_health",
    ]


def _step_from_event(event_type: str, event: ExecutionAuditEvent | None) -> ExecutionAuditStep:
    if event is None:
        return ExecutionAuditStep(
            event_type=event_type,
            status="MISSING",
            passed=None,
            timestamp="",
            trade_date="",
            strategy_id="",
            order_count=0,
            notional=0.0,
            detail="event not found in latest refresh cycle",
            artifact_paths={},
        )
    return ExecutionAuditStep(
        event_type=event_type,
        status=event.status,
        passed=event.passed,
        timestamp=event.timestamp,
        trade_date=event.trade_date,
        strategy_id=event.strategy_id,
        order_count=event.order_count,
        notional=event.notional,
        detail=_event_detail(event),
        artifact_paths=event.artifact_paths,
    )


def _event_detail(event: ExecutionAuditEvent) -> str:
    if event.event_type == "execution_authorization":
        failed = event.summary.get("failed_checks")
        return "failed_checks=" + ",".join(str(value) for value in failed) if isinstance(failed, list) and failed else "authorization passed"
    if event.event_type == "broker_adapter_contract":
        return str(event.summary.get("issue", "")) or "contract passed"
    if event.event_type in {"manual_package", "manual_package_existing"}:
        return f"rebuild={event.summary.get('rebuild', '-')}"
    if event.event_type == "manual_fill_validation":
        return f"issues={event.summary.get('issue_count', 0)}, allow_incomplete={event.summary.get('allow_incomplete', False)}"
    if event.event_type == "manual_reconciliation":
        return str(event.summary.get("reason", event.summary.get("report_id", ""))) or "reconciliation complete"
    if event.event_type == "execution_day_end":
        blocked = event.summary.get("blocked_artifacts")
        pending = event.summary.get("pending_artifacts")
        return f"blocked={blocked or []}, pending={pending or []}"
    if event.event_type == "config_health":
        return f"errors={event.summary.get('errors', 0)}, warnings={event.summary.get('warnings', 0)}"
    return ""


def _first_non_empty(values: object) -> str:
    for value in values:
        if value:
            return str(value)
    return ""


def _artifact_summary(paths: dict[str, str]) -> str:
    if not paths:
        return "-"
    return "; ".join(f"{name}={path}" for name, path in sorted(paths.items()))


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
