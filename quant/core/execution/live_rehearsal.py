from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from quant.core.execution.authorization import (
    ExecutionAuthorizationReport,
    ExecutionPolicy,
    build_execution_authorization_report_from_submission,
)


@dataclass(frozen=True)
class LiveRehearsalReport:
    rehearsal_id: str
    status: str
    source_submission_path: str
    policy_path: str
    live_adapter: str
    trade_date: str
    strategy_id: str
    order_count: int
    notional: float
    default_authorization: ExecutionAuthorizationReport
    policy_authorization: ExecutionAuthorizationReport | None

    def to_dict(self) -> dict[str, object]:
        return {
            "rehearsal_id": self.rehearsal_id,
            "status": self.status,
            "source_submission_path": self.source_submission_path,
            "policy_path": self.policy_path,
            "live_adapter": self.live_adapter,
            "trade_date": self.trade_date,
            "strategy_id": self.strategy_id,
            "order_count": self.order_count,
            "notional": self.notional,
            "default_authorization": self.default_authorization.to_dict(),
            "policy_authorization": self.policy_authorization.to_dict()
            if self.policy_authorization is not None
            else None,
        }


def build_live_rehearsal_report(
    *,
    broker_submission_path: Path,
    live_adapter: str = "qmt",
    policy_path: Path | None = None,
) -> LiveRehearsalReport:
    source = _read_object(broker_submission_path)
    rehearsal_submission = _live_submission(source, live_adapter)
    default_authorization = build_execution_authorization_report_from_submission(
        rehearsal_submission,
        policy=ExecutionPolicy(),
        policy_path="default dry-run only",
    )
    policy_authorization = None
    if policy_path is not None:
        policy_authorization = build_execution_authorization_report_from_submission(
            rehearsal_submission,
            policy=ExecutionPolicy.from_dict(_read_object(policy_path)),
            policy_path=str(policy_path),
        )
    return LiveRehearsalReport(
        rehearsal_id=uuid4().hex,
        status=_status(default_authorization, policy_authorization),
        source_submission_path=str(broker_submission_path),
        policy_path=str(policy_path) if policy_path else "",
        live_adapter=live_adapter,
        trade_date=str(rehearsal_submission.get("trade_date", "")),
        strategy_id=str(rehearsal_submission.get("strategy_id", "")),
        order_count=int(rehearsal_submission.get("order_count", 0) or 0),
        notional=default_authorization.notional,
        default_authorization=default_authorization,
        policy_authorization=policy_authorization,
    )


def render_live_rehearsal_markdown(report: LiveRehearsalReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Live Adapter", report.live_adapter],
        ["Trade Date", report.trade_date],
        ["Strategy", report.strategy_id],
        ["Orders", report.order_count],
        ["Notional", f"{report.notional:,.2f}"],
        ["Source Submission", report.source_submission_path],
        ["Policy", report.policy_path or "-"],
    ]
    lines = [
        "# Live Execution Rehearsal",
        "",
        _table(["Metric", "Value"], summary_rows),
        "",
        "## Default Authorization",
        _authorization_table(report.default_authorization),
    ]
    if report.policy_authorization is not None:
        lines.extend(["", "## Policy Authorization", _authorization_table(report.policy_authorization)])
    lines.append("")
    return "\n".join(lines)


def write_live_rehearsal_json(report: LiveRehearsalReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_live_rehearsal_markdown(report: LiveRehearsalReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_live_rehearsal_markdown(report), encoding="utf-8")
    return path


def _live_submission(source: dict[str, Any], live_adapter: str) -> dict[str, Any]:
    submission = dict(source)
    submission["mode"] = "LIVE"
    submission["adapter"] = live_adapter
    orders = submission.get("orders", [])
    if isinstance(orders, list):
        submission["orders"] = [
            {**order, "adapter": live_adapter, "status": "LIVE_REHEARSAL"}
            if isinstance(order, dict)
            else order
            for order in orders
        ]
    return submission


def _status(
    default_authorization: ExecutionAuthorizationReport,
    policy_authorization: ExecutionAuthorizationReport | None,
) -> str:
    if default_authorization.passed:
        return "FAIL_OPEN"
    if policy_authorization is None:
        return "EXPECTED_BLOCK"
    if policy_authorization.passed:
        return "PASS"
    return "POLICY_BLOCKED"


def _authorization_table(report: ExecutionAuthorizationReport) -> str:
    rows = [
        ["Status", report.status],
        ["Passed", report.passed],
        ["Mode", report.mode],
        ["Adapter", report.adapter],
        ["Policy", report.policy_path],
        ["Failed Checks", _failed_checks(report)],
    ]
    return _table(["Metric", "Value"], rows)


def _failed_checks(report: ExecutionAuthorizationReport) -> str:
    failed = [check.name for check in report.checks if not check.passed]
    return ";".join(failed) if failed else "-"


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"live rehearsal input not found: {path}")
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
