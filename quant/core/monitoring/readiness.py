from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    severity: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReadinessReport:
    status: str
    paper_ready: bool
    live_ready: bool
    checks: list[ReadinessCheck]
    alerts_path: str
    pretrade_gate_path: str
    stability_path: str
    qmt_available: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "paper_ready": self.paper_ready,
            "live_ready": self.live_ready,
            "checks": [check.to_dict() for check in self.checks],
            "alerts_path": self.alerts_path,
            "pretrade_gate_path": self.pretrade_gate_path,
            "stability_path": self.stability_path,
            "qmt_available": self.qmt_available,
        }


def build_readiness_report(
    *,
    alerts_path: Path,
    pretrade_gate_path: Path,
    stability_path: Path,
    qmt_available: bool = False,
) -> ReadinessReport:
    alerts = _read_object(alerts_path)
    pretrade = _read_object(pretrade_gate_path)
    stability = _read_object(stability_path)
    checks = [
        _alerts_check(alerts),
        _pretrade_check(pretrade),
        _stability_latest_check(stability),
        _stability_window_check(stability),
        _qmt_check(qmt_available),
    ]
    paper_ready = all(
        check.passed
        for check in checks
        if check.name in {"alerts", "pretrade_gate", "latest_stability"}
    )
    live_ready = paper_ready and all(
        check.passed
        for check in checks
        if check.name in {"stability_window", "qmt_interface"}
    )
    status = "LIVE_READY" if live_ready else "PAPER_READY" if paper_ready else "BLOCKED"
    return ReadinessReport(
        status=status,
        paper_ready=paper_ready,
        live_ready=live_ready,
        checks=checks,
        alerts_path=str(alerts_path),
        pretrade_gate_path=str(pretrade_gate_path),
        stability_path=str(stability_path),
        qmt_available=qmt_available,
    )


def write_readiness_json(report: ReadinessReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_readiness_markdown(report: ReadinessReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_readiness_markdown(report), encoding="utf-8")
    return path


def render_readiness_markdown(report: ReadinessReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Paper Ready", report.paper_ready],
        ["Live Ready", report.live_ready],
        ["QMT Available", report.qmt_available],
    ]
    check_rows = [
        [check.name, check.passed, check.severity, check.detail]
        for check in report.checks
    ]
    return "\n".join(
        [
            "# Quant Readiness Report",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            _table(["Check", "Passed", "Severity", "Detail"], check_rows),
            "",
            f"Alerts: `{report.alerts_path}`",
            f"Pre-Trade Gate: `{report.pretrade_gate_path}`",
            f"Stability: `{report.stability_path}`",
            "",
        ]
    )


def _alerts_check(alerts: dict[str, Any]) -> ReadinessCheck:
    status = str(alerts.get("status", "UNKNOWN")).upper()
    passed = bool(alerts.get("passed", False)) and status == "OK"
    return ReadinessCheck(
        name="alerts",
        passed=passed,
        severity=str(alerts.get("highest_severity", "UNKNOWN")),
        detail=f"alerts status={status}",
    )


def _pretrade_check(pretrade: dict[str, Any]) -> ReadinessCheck:
    status = str(pretrade.get("status", "UNKNOWN")).upper()
    passed = bool(pretrade.get("passed", False)) and status == "GO"
    return ReadinessCheck(
        name="pretrade_gate",
        passed=passed,
        severity="CRITICAL",
        detail=f"pretrade status={status}",
    )


def _stability_latest_check(stability: dict[str, Any]) -> ReadinessCheck:
    latest_stable = bool(stability.get("latest_stable", False))
    latest_date = str(stability.get("latest_trade_date", ""))
    return ReadinessCheck(
        name="latest_stability",
        passed=latest_stable,
        severity="WARNING",
        detail=f"latest_trade_date={latest_date or '-'}",
    )


def _stability_window_check(stability: dict[str, Any]) -> ReadinessCheck:
    ready = bool(stability.get("ready_for_live", False))
    observed = int(stability.get("observed_days", 0) or 0)
    target = int(stability.get("target_days", 20) or 20)
    unstable = int(stability.get("unstable_days", 0) or 0)
    return ReadinessCheck(
        name="stability_window",
        passed=ready,
        severity="WARNING",
        detail=f"observed={observed}/{target}, unstable_days={unstable}",
    )


def _qmt_check(qmt_available: bool) -> ReadinessCheck:
    return ReadinessCheck(
        name="qmt_interface",
        passed=qmt_available,
        severity="CRITICAL",
        detail="qmt interface available" if qmt_available else "qmt interface not configured",
    )


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"readiness artifact not found: {path}")
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
