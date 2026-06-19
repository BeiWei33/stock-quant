from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionPolicy:
    auto_trade_enabled: bool = False
    allowed_modes: tuple[str, ...] = ("DRY_RUN",)
    allowed_adapters: tuple[str, ...] = ("dry_run",)
    approved_trade_date: str = ""
    approved_strategy_id: str = ""
    approval_id: str = ""
    approved_by: str = ""
    expires_at: str = ""
    max_order_count: int = 0
    max_notional: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionPolicy":
        return cls(
            auto_trade_enabled=bool(payload.get("auto_trade_enabled", False)),
            allowed_modes=tuple(str(value).upper() for value in payload.get("allowed_modes", ["DRY_RUN"])),
            allowed_adapters=tuple(str(value) for value in payload.get("allowed_adapters", ["dry_run"])),
            approved_trade_date=str(payload.get("approved_trade_date", "")),
            approved_strategy_id=str(payload.get("approved_strategy_id", "")),
            approval_id=str(payload.get("approval_id", "")),
            approved_by=str(payload.get("approved_by", "")),
            expires_at=str(payload.get("expires_at", "")),
            max_order_count=int(payload.get("max_order_count", 0) or 0),
            max_notional=float(payload.get("max_notional", 0.0) or 0.0),
        )

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["allowed_modes"] = list(self.allowed_modes)
        data["allowed_adapters"] = list(self.allowed_adapters)
        return data


@dataclass(frozen=True)
class ExecutionAuthorizationCheck:
    name: str
    passed: bool
    severity: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionAuthorizationReport:
    status: str
    passed: bool
    mode: str
    adapter: str
    trade_date: str
    strategy_id: str
    order_count: int
    notional: float
    policy_path: str
    checks: list[ExecutionAuthorizationCheck]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed": self.passed,
            "mode": self.mode,
            "adapter": self.adapter,
            "trade_date": self.trade_date,
            "strategy_id": self.strategy_id,
            "order_count": self.order_count,
            "notional": self.notional,
            "policy_path": self.policy_path,
            "checks": [check.to_dict() for check in self.checks],
        }


def build_execution_authorization_report(
    *,
    broker_submission_path: Path,
    policy_path: Path | None = None,
    now: datetime | None = None,
) -> ExecutionAuthorizationReport:
    broker = _read_object(broker_submission_path)
    policy = _load_policy(policy_path)
    return build_execution_authorization_report_from_submission(
        broker,
        policy=policy,
        policy_path=str(policy_path) if policy_path else "",
        now=now,
    )


def build_execution_authorization_report_from_submission(
    broker: dict[str, Any],
    *,
    policy: ExecutionPolicy,
    policy_path: str = "",
    now: datetime | None = None,
) -> ExecutionAuthorizationReport:
    mode = str(broker.get("mode", "")).upper()
    adapter = str(broker.get("adapter", ""))
    trade_date = str(broker.get("trade_date", ""))
    strategy_id = str(broker.get("strategy_id", ""))
    order_count = int(broker.get("order_count", 0) or 0)
    notional = _notional(broker.get("orders", []))
    checks = [
        _mode_check(mode, policy),
        _adapter_check(adapter, policy),
        _auto_trade_check(mode, policy),
        _approval_identity_check(mode, policy),
        _approval_scope_check(
            mode=mode,
            trade_date=trade_date,
            strategy_id=strategy_id,
            policy=policy,
        ),
        _expiry_check(mode, policy, now or datetime.now(UTC)),
        _order_count_check(order_count, policy),
        _notional_check(notional, policy),
    ]
    passed = all(check.passed for check in checks)
    return ExecutionAuthorizationReport(
        status="GO" if passed else "BLOCK",
        passed=passed,
        mode=mode,
        adapter=adapter,
        trade_date=trade_date,
        strategy_id=strategy_id,
        order_count=order_count,
        notional=notional,
        policy_path=policy_path,
        checks=checks,
    )


def render_execution_authorization_markdown(report: ExecutionAuthorizationReport) -> str:
    rows = [
        ["Status", report.status],
        ["Passed", report.passed],
        ["Mode", report.mode or "UNKNOWN"],
        ["Adapter", report.adapter or "UNKNOWN"],
        ["Trade Date", report.trade_date or "-"],
        ["Strategy", report.strategy_id or "-"],
        ["Orders", report.order_count],
        ["Notional", f"{report.notional:,.2f}"],
        ["Policy", report.policy_path or "default dry-run only"],
    ]
    check_rows = [
        [check.name, "PASS" if check.passed else "FAIL", check.severity, check.detail]
        for check in report.checks
    ]
    return "\n".join(
        [
            "# Execution Authorization Report",
            "",
            _table(["Field", "Value"], rows),
            "",
            "## Checks",
            _table(["Check", "Result", "Severity", "Detail"], check_rows),
            "",
        ]
    )


def write_execution_authorization_json(report: ExecutionAuthorizationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_execution_authorization_markdown(report: ExecutionAuthorizationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_execution_authorization_markdown(report), encoding="utf-8")
    return path


def build_execution_policy(
    *,
    mode: str = "DRY_RUN",
    adapter: str = "dry_run",
    trade_date: str = "",
    strategy_id: str = "",
    approval_id: str = "",
    approved_by: str = "",
    expires_at: str = "",
    max_order_count: int = 0,
    max_notional: float = 0.0,
    auto_trade_enabled: bool | None = None,
) -> ExecutionPolicy:
    normalized_mode = mode.upper()
    if normalized_mode != "DRY_RUN":
        missing = [
            name
            for name, value in {
                "trade_date": trade_date,
                "strategy_id": strategy_id,
                "approval_id": approval_id,
                "approved_by": approved_by,
                "expires_at": expires_at,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError("non-dry-run policy requires: " + ", ".join(missing))
    enabled = normalized_mode != "DRY_RUN" if auto_trade_enabled is None else auto_trade_enabled
    return ExecutionPolicy(
        auto_trade_enabled=enabled,
        allowed_modes=(normalized_mode,),
        allowed_adapters=(adapter,),
        approved_trade_date=trade_date,
        approved_strategy_id=strategy_id,
        approval_id=approval_id,
        approved_by=approved_by,
        expires_at=expires_at,
        max_order_count=max_order_count,
        max_notional=max_notional,
    )


def render_execution_policy_markdown(policy: ExecutionPolicy) -> str:
    rows = [
        ["Auto Trade Enabled", policy.auto_trade_enabled],
        ["Allowed Modes", ", ".join(policy.allowed_modes)],
        ["Allowed Adapters", ", ".join(policy.allowed_adapters)],
        ["Approved Trade Date", policy.approved_trade_date or "-"],
        ["Approved Strategy", policy.approved_strategy_id or "-"],
        ["Approval ID", policy.approval_id or "-"],
        ["Approved By", policy.approved_by or "-"],
        ["Expires At", policy.expires_at or "-"],
        ["Max Order Count", policy.max_order_count or "unlimited"],
        ["Max Notional", policy.max_notional or "unlimited"],
    ]
    return "\n".join(
        [
            "# Execution Policy",
            "",
            _table(["Field", "Value"], rows),
            "",
        ]
    )


def write_execution_policy_json(policy: ExecutionPolicy, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_execution_policy_markdown(policy: ExecutionPolicy, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_execution_policy_markdown(policy), encoding="utf-8")
    return path


def _load_policy(path: Path | None) -> ExecutionPolicy:
    if path is None:
        return ExecutionPolicy()
    payload = _read_object(path)
    return ExecutionPolicy.from_dict(payload)


def _mode_check(mode: str, policy: ExecutionPolicy) -> ExecutionAuthorizationCheck:
    passed = mode in policy.allowed_modes
    return ExecutionAuthorizationCheck(
        "execution_mode_allowed",
        passed,
        "CRITICAL",
        f"mode={mode or 'UNKNOWN'}, allowed={','.join(policy.allowed_modes)}",
    )


def _adapter_check(adapter: str, policy: ExecutionPolicy) -> ExecutionAuthorizationCheck:
    passed = adapter in policy.allowed_adapters
    return ExecutionAuthorizationCheck(
        "execution_adapter_allowed",
        passed,
        "CRITICAL",
        f"adapter={adapter or 'UNKNOWN'}, allowed={','.join(policy.allowed_adapters)}",
    )


def _auto_trade_check(mode: str, policy: ExecutionPolicy) -> ExecutionAuthorizationCheck:
    passed = mode == "DRY_RUN" or policy.auto_trade_enabled
    return ExecutionAuthorizationCheck(
        "auto_trade_enabled",
        passed,
        "CRITICAL",
        "dry-run does not require auto_trade" if mode == "DRY_RUN" else f"auto_trade_enabled={policy.auto_trade_enabled}",
    )


def _approval_identity_check(mode: str, policy: ExecutionPolicy) -> ExecutionAuthorizationCheck:
    passed = mode == "DRY_RUN" or bool(policy.approval_id and policy.approved_by)
    return ExecutionAuthorizationCheck(
        "manual_approval_present",
        passed,
        "CRITICAL",
        "dry-run does not require manual approval"
        if mode == "DRY_RUN"
        else f"approval_id={policy.approval_id or '-'}, approved_by={policy.approved_by or '-'}",
    )


def _approval_scope_check(
    *,
    mode: str,
    trade_date: str,
    strategy_id: str,
    policy: ExecutionPolicy,
) -> ExecutionAuthorizationCheck:
    date_ok = not policy.approved_trade_date or policy.approved_trade_date == trade_date
    strategy_ok = not policy.approved_strategy_id or policy.approved_strategy_id == strategy_id
    passed = mode == "DRY_RUN" or (date_ok and strategy_ok)
    return ExecutionAuthorizationCheck(
        "manual_approval_scope",
        passed,
        "CRITICAL",
        "dry-run does not require approval scope"
        if mode == "DRY_RUN"
        else (
            f"trade_date={trade_date or '-'} expected={policy.approved_trade_date or '*'}, "
            f"strategy={strategy_id or '-'} expected={policy.approved_strategy_id or '*'}"
        ),
    )


def _expiry_check(mode: str, policy: ExecutionPolicy, now: datetime) -> ExecutionAuthorizationCheck:
    if mode == "DRY_RUN":
        return ExecutionAuthorizationCheck(
            "manual_approval_not_expired",
            True,
            "CRITICAL",
            "dry-run does not require approval expiry",
        )
    if not policy.expires_at:
        return ExecutionAuthorizationCheck(
            "manual_approval_not_expired",
            False,
            "CRITICAL",
            "expires_at is required for non-dry-run execution",
        )
    expires = datetime.fromisoformat(policy.expires_at.replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    passed = now.astimezone(UTC) <= expires.astimezone(UTC)
    return ExecutionAuthorizationCheck(
        "manual_approval_not_expired",
        passed,
        "CRITICAL",
        f"expires_at={expires.isoformat()}, now={now.astimezone(UTC).isoformat()}",
    )


def _order_count_check(order_count: int, policy: ExecutionPolicy) -> ExecutionAuthorizationCheck:
    passed = policy.max_order_count <= 0 or order_count <= policy.max_order_count
    return ExecutionAuthorizationCheck(
        "order_count_limit",
        passed,
        "CRITICAL",
        f"order_count={order_count}, max={policy.max_order_count or 'unlimited'}",
    )


def _notional_check(notional: float, policy: ExecutionPolicy) -> ExecutionAuthorizationCheck:
    passed = policy.max_notional <= 0 or notional <= policy.max_notional
    return ExecutionAuthorizationCheck(
        "notional_limit",
        passed,
        "CRITICAL",
        f"notional={notional:.2f}, max={policy.max_notional or 'unlimited'}",
    )


def _notional(orders: object) -> float:
    if not isinstance(orders, list):
        return 0.0
    total = 0.0
    for order in orders:
        if not isinstance(order, dict):
            continue
        total += abs(float(order.get("quantity", 0) or 0) * float(order.get("price", 0.0) or 0.0))
    return total


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"execution artifact not found: {path}")
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
