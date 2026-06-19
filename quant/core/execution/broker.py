from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class BrokerOrder:
    broker_order_id: str
    order_id: str
    account_id: str
    strategy_id: str
    ts_code: str
    side: str
    quantity: int
    price: float
    target_weight: float
    trade_date: str
    status: str
    adapter: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BrokerSubmissionPackage:
    submission_id: str
    adapter: str
    mode: str
    created_at: str
    trade_date: str
    strategy_id: str
    risk_guard_allowed: bool
    risk_guard_report_path: str
    order_count: int
    orders: list[BrokerOrder]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["orders"] = [order.to_dict() for order in self.orders]
        return data


def build_dry_run_submission(
    *,
    plan_path: Path,
    risk_guard_report_path: Path,
    adapter: str = "dry_run",
) -> BrokerSubmissionPackage:
    plan = _read_object(plan_path)
    risk_guard = _read_object(risk_guard_report_path)
    if not bool(risk_guard.get("allowed", False)):
        rejected = risk_guard.get("rejected_orders", 0)
        raise ValueError(f"risk guard did not allow broker submission: rejected_orders={rejected}")

    raw_orders = plan.get("order_intents", [])
    if not isinstance(raw_orders, list):
        raise ValueError("paper plan order_intents must be a list")

    orders = [_broker_order(raw_order, adapter) for raw_order in raw_orders]
    return BrokerSubmissionPackage(
        submission_id=uuid4().hex,
        adapter=adapter,
        mode="DRY_RUN",
        created_at=datetime.now(UTC).isoformat(),
        trade_date=str(plan.get("trade_date", "")),
        strategy_id=str(plan.get("strategy", {}).get("strategy_id", "")) if isinstance(plan.get("strategy"), dict) else "",
        risk_guard_allowed=True,
        risk_guard_report_path=str(risk_guard_report_path),
        order_count=len(orders),
        orders=orders,
    )


def render_submission_markdown(package: BrokerSubmissionPackage) -> str:
    rows = [
        ["Submission", package.submission_id],
        ["Adapter", package.adapter],
        ["Mode", package.mode],
        ["Trade Date", package.trade_date],
        ["Strategy", package.strategy_id],
        ["Risk Guard", "ALLOW" if package.risk_guard_allowed else "REJECT"],
        ["Orders", package.order_count],
    ]
    lines = [
        "# Broker Submission Package",
        "",
        _table(["Field", "Value"], rows),
        "",
        "## Orders",
    ]
    if not package.orders:
        lines.append("_No orders._")
    else:
        lines.append(
            _table(
                ["Broker Order", "Order", "Code", "Side", "Qty", "Price", "Status"],
                [
                    [
                        order.broker_order_id,
                        order.order_id,
                        order.ts_code,
                        order.side,
                        order.quantity,
                        f"{order.price:.4f}",
                        order.status,
                    ]
                    for order in package.orders
                ],
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_submission_json(package: BrokerSubmissionPackage, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(package.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_submission_markdown(package: BrokerSubmissionPackage, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_submission_markdown(package), encoding="utf-8")
    return path


def _broker_order(raw_order: object, adapter: str) -> BrokerOrder:
    if not isinstance(raw_order, dict):
        raise ValueError("paper plan order_intents must contain objects")
    order_id = str(raw_order.get("order_id", ""))
    if not order_id:
        raise ValueError("paper plan order is missing order_id")
    return BrokerOrder(
        broker_order_id=f"DRYRUN:{order_id}",
        order_id=order_id,
        account_id=str(raw_order.get("account_id", "")),
        strategy_id=str(raw_order.get("strategy_id", "")),
        ts_code=str(raw_order.get("ts_code", "")),
        side=str(raw_order.get("side", "")).upper(),
        quantity=int(raw_order.get("quantity", 0)),
        price=float(raw_order.get("price", 0.0)),
        target_weight=float(raw_order.get("target_weight", 0.0)),
        trade_date=str(raw_order.get("trade_date", "")),
        status="DRY_RUN_ACCEPTED",
        adapter=adapter,
    )


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
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
