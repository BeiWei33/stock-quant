from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


SEVERITY_RANK = {
    "INFO": 0,
    "WARNING": 1,
    "CRITICAL": 2,
}


@dataclass(frozen=True)
class Alert:
    name: str
    severity: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AlertEvaluation:
    status: str
    passed: bool
    highest_severity: str
    alerts: list[Alert]
    status_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed": self.passed,
            "highest_severity": self.highest_severity,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "status_path": self.status_path,
        }


def evaluate_monitor_alerts(status_path: Path) -> AlertEvaluation:
    status = _read_json(status_path)
    alerts = [
        _monitor_level_alert(status),
        _pretrade_gate_alert(status),
        _risk_guard_alert(status),
        _reconciliation_alert(status),
        _health_check_alert(status),
        _drawdown_alert(status),
    ]
    failed = [alert for alert in alerts if not alert.passed]
    highest = _highest_severity(failed)
    return AlertEvaluation(
        status="ALERT" if failed else "OK",
        passed=not failed,
        highest_severity=highest,
        alerts=alerts,
        status_path=str(status_path),
    )


def write_alerts_json(evaluation: AlertEvaluation, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(evaluation.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_alerts_markdown(evaluation: AlertEvaluation, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_alerts_markdown(evaluation), encoding="utf-8")
    return path


def render_alerts_markdown(evaluation: AlertEvaluation) -> str:
    rows = [
        [alert.name, alert.severity, alert.passed, alert.detail]
        for alert in evaluation.alerts
    ]
    return "\n".join(
        [
            f"# Quant Monitor Alerts - {evaluation.status}",
            "",
            f"Highest Severity: `{evaluation.highest_severity}`",
            "",
            _table(["Alert", "Severity", "Passed", "Detail"], rows),
            "",
            f"Status: `{evaluation.status_path}`",
            "",
        ]
    )


def _monitor_level_alert(status: dict[str, Any]) -> Alert:
    level = str(status.get("level", "UNKNOWN")).upper()
    passed = level == "INFO"
    severity = "CRITICAL" if level == "CRITICAL" else "WARNING"
    return Alert(
        name="monitor_level",
        severity=severity,
        passed=passed,
        detail=f"monitor level is {level}",
    )


def _pretrade_gate_alert(status: dict[str, Any]) -> Alert:
    gate_status = str(status.get("latest_pretrade_gate_status", "UNKNOWN")).upper()
    block_runs = _int(status.get("pretrade_gate_block_runs"))
    failed_checks = str(status.get("pretrade_gate_failed_checks", ""))
    passed = gate_status in {"GO", "UNKNOWN"} and block_runs == 0
    detail = f"latest={gate_status}, block_runs={block_runs}"
    if failed_checks:
        detail += f", failed_checks={failed_checks}"
    return Alert(
        name="pretrade_gate",
        severity="CRITICAL",
        passed=passed,
        detail=detail,
    )


def _risk_guard_alert(status: dict[str, Any]) -> Alert:
    rejected_runs = _int(status.get("risk_guard_rejected_runs"))
    rejected_orders = _int(status.get("risk_guard_rejected_orders"))
    return Alert(
        name="risk_guard",
        severity="CRITICAL",
        passed=rejected_runs == 0 and rejected_orders == 0,
        detail=f"rejected_runs={rejected_runs}, rejected_orders={rejected_orders}",
    )


def _reconciliation_alert(status: dict[str, Any]) -> Alert:
    diff_runs = _int(status.get("reconciliation_diff_runs"))
    diff_count = _int(status.get("reconciliation_diff_count"))
    return Alert(
        name="reconciliation",
        severity="WARNING",
        passed=diff_runs == 0 and diff_count == 0,
        detail=f"diff_runs={diff_runs}, diff_count={diff_count}",
    )


def _health_check_alert(status: dict[str, Any]) -> Alert:
    failed_count = _int(status.get("failed_health_count"))
    failed_checks = str(status.get("failed_health_checks", ""))
    detail = f"failed_count={failed_count}"
    if failed_checks:
        detail += f", failed_checks={failed_checks}"
    return Alert(
        name="health_checks",
        severity="WARNING",
        passed=failed_count == 0,
        detail=detail,
    )


def _drawdown_alert(status: dict[str, Any]) -> Alert:
    max_drawdown = _float(status.get("max_drawdown"))
    severity = "CRITICAL" if max_drawdown <= -0.15 else "WARNING"
    return Alert(
        name="drawdown",
        severity=severity,
        passed=max_drawdown > -0.10,
        detail=f"max_drawdown={max_drawdown:.2%}",
    )


def _highest_severity(alerts: list[Alert]) -> str:
    if not alerts:
        return "INFO"
    return max(alerts, key=lambda alert: SEVERITY_RANK.get(alert.severity, 0)).severity


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"monitor status not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _int(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


def _float(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
