from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from quant.core.execution.authorization import (
    ExecutionPolicy,
    build_execution_authorization_report_from_submission,
)


@dataclass(frozen=True)
class PreTradeCheck:
    name: str
    passed: bool
    severity: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PreTradeGateReport:
    status: str
    passed: bool
    checks: list[PreTradeCheck]
    monitor_status_path: str
    risk_guard_path: str
    broker_submission_path: str
    execution_policy_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
            "monitor_status_path": self.monitor_status_path,
            "risk_guard_path": self.risk_guard_path,
            "broker_submission_path": self.broker_submission_path,
            "execution_policy_path": self.execution_policy_path,
        }


def build_pretrade_gate_report(
    *,
    monitor_status_path: Path,
    risk_guard_path: Path,
    broker_submission_path: Path,
    execution_policy_path: Path | None = None,
    allow_monitor_warning: bool = False,
) -> PreTradeGateReport:
    monitor = _read_object(monitor_status_path)
    risk_guard = _read_object(risk_guard_path)
    broker = _read_object(broker_submission_path)
    policy = ExecutionPolicy.from_dict(_read_object(execution_policy_path)) if execution_policy_path else ExecutionPolicy()
    authorization = build_execution_authorization_report_from_submission(
        broker,
        policy=policy,
        policy_path=str(execution_policy_path) if execution_policy_path else "",
    )
    checks = [
        _monitor_check(monitor, allow_warning=allow_monitor_warning),
        _risk_guard_check(risk_guard),
        _broker_risk_check(broker),
        _order_count_check(risk_guard, broker),
        _broker_mode_check(broker),
        *[
            PreTradeCheck(
                f"execution_{check.name}",
                check.passed,
                check.severity,
                check.detail,
            )
            for check in authorization.checks
        ],
    ]
    passed = all(check.passed for check in checks)
    return PreTradeGateReport(
        status="GO" if passed else "BLOCK",
        passed=passed,
        checks=checks,
        monitor_status_path=str(monitor_status_path),
        risk_guard_path=str(risk_guard_path),
        broker_submission_path=str(broker_submission_path),
        execution_policy_path=str(execution_policy_path) if execution_policy_path else "",
    )


def render_pretrade_gate_markdown(report: PreTradeGateReport) -> str:
    rows = [
        ["Status", report.status],
        ["Passed", report.passed],
        ["Monitor", report.monitor_status_path],
        ["Risk Guard", report.risk_guard_path],
        ["Broker Submission", report.broker_submission_path],
        ["Execution Policy", report.execution_policy_path or "default dry-run only"],
    ]
    check_rows = [
        [check.name, "PASS" if check.passed else "FAIL", check.severity, check.detail]
        for check in report.checks
    ]
    return "\n".join(
        [
            "# Pre-Trade Gate Report",
            "",
            _table(["Field", "Value"], rows),
            "",
            "## Checks",
            _table(["Check", "Result", "Severity", "Detail"], check_rows),
            "",
        ]
    )


def write_pretrade_gate_json(report: PreTradeGateReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_pretrade_gate_markdown(report: PreTradeGateReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_pretrade_gate_markdown(report), encoding="utf-8")
    return path


def _monitor_check(monitor: dict[str, Any], *, allow_warning: bool) -> PreTradeCheck:
    level = str(monitor.get("level", "UNKNOWN")).upper()
    if level == "INFO" or (allow_warning and level == "WARNING"):
        return PreTradeCheck("monitor_status", True, level, f"monitor level is {level}")
    return PreTradeCheck("monitor_status", False, level, f"monitor level is {level}")


def _risk_guard_check(risk_guard: dict[str, Any]) -> PreTradeCheck:
    allowed = bool(risk_guard.get("allowed", False))
    rejected = int(risk_guard.get("rejected_orders", 0) or 0)
    return PreTradeCheck(
        "risk_guard_allowed",
        allowed and rejected == 0,
        "CRITICAL",
        f"allowed={allowed}, rejected_orders={rejected}",
    )


def _broker_risk_check(broker: dict[str, Any]) -> PreTradeCheck:
    allowed = bool(broker.get("risk_guard_allowed", False))
    return PreTradeCheck(
        "broker_risk_guard_link",
        allowed,
        "CRITICAL",
        f"broker risk_guard_allowed={allowed}",
    )


def _order_count_check(risk_guard: dict[str, Any], broker: dict[str, Any]) -> PreTradeCheck:
    accepted = int(risk_guard.get("accepted_orders", 0) or 0)
    order_count = int(broker.get("order_count", 0) or 0)
    return PreTradeCheck(
        "order_count_match",
        accepted == order_count,
        "CRITICAL",
        f"risk_guard accepted_orders={accepted}, broker order_count={order_count}",
    )


def _broker_mode_check(broker: dict[str, Any]) -> PreTradeCheck:
    mode = str(broker.get("mode", "")).upper()
    passed = mode in {"DRY_RUN", "LIVE"}
    return PreTradeCheck("broker_mode", passed, "INFO", f"broker mode is {mode or 'UNKNOWN'}")


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"pre-trade artifact not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
