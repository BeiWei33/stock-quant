from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ManualExecutionOrder:
    broker_order_id: str
    order_id: str
    account_id: str
    strategy_id: str
    trade_date: str
    ts_code: str
    side: str
    quantity: int
    limit_price: float
    target_weight: float
    estimated_notional: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ManualExecutionPackage:
    package_id: str
    created_at: str
    status: str
    broker_submission_path: str
    order_ticket_path: str
    fill_template_path: str
    trade_date: str
    strategy_id: str
    order_count: int
    estimated_notional: float
    orders: list[ManualExecutionOrder]

    def to_dict(self) -> dict[str, object]:
        return {
            "package_id": self.package_id,
            "created_at": self.created_at,
            "status": self.status,
            "broker_submission_path": self.broker_submission_path,
            "order_ticket_path": self.order_ticket_path,
            "fill_template_path": self.fill_template_path,
            "trade_date": self.trade_date,
            "strategy_id": self.strategy_id,
            "order_count": self.order_count,
            "estimated_notional": self.estimated_notional,
            "orders": [order.to_dict() for order in self.orders],
        }


def build_manual_execution_package(
    *,
    broker_submission_path: Path,
    order_ticket_path: Path,
    fill_template_path: Path,
) -> ManualExecutionPackage:
    submission = _read_object(broker_submission_path)
    if str(submission.get("mode", "")).upper() != "DRY_RUN":
        raise ValueError("manual execution package can only be built from a dry-run broker submission")
    if not bool(submission.get("risk_guard_allowed", False)):
        raise ValueError("manual execution package requires risk_guard_allowed=true")
    raw_orders = submission.get("orders", [])
    if not isinstance(raw_orders, list):
        raise ValueError("broker submission orders must be a list")
    orders = [_manual_order(raw_order) for raw_order in raw_orders]
    package = ManualExecutionPackage(
        package_id=uuid4().hex,
        created_at=datetime.now(UTC).isoformat(),
        status="READY",
        broker_submission_path=str(broker_submission_path),
        order_ticket_path=str(order_ticket_path),
        fill_template_path=str(fill_template_path),
        trade_date=str(submission.get("trade_date", "")),
        strategy_id=str(submission.get("strategy_id", "")),
        order_count=len(orders),
        estimated_notional=sum(order.estimated_notional for order in orders),
        orders=orders,
    )
    write_order_ticket_csv(package, order_ticket_path)
    write_fill_template_csv(package, fill_template_path)
    return package


def write_manual_execution_json(package: ManualExecutionPackage, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(package.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_manual_execution_markdown(package: ManualExecutionPackage, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_manual_execution_markdown(package), encoding="utf-8")
    return path


def write_order_ticket_csv(package: ManualExecutionPackage, path: Path) -> Path:
    rows = [
        {
            "trade_date": order.trade_date,
            "ts_code": order.ts_code,
            "side": order.side,
            "quantity": order.quantity,
            "limit_price": f"{order.limit_price:.4f}",
            "estimated_notional": f"{order.estimated_notional:.2f}",
            "account_id": order.account_id,
            "strategy_id": order.strategy_id,
            "order_id": order.order_id,
            "broker_order_id": order.broker_order_id,
            "manual_status": "PENDING",
            "submitted_quantity": "",
            "submitted_price": "",
            "operator_note": "",
        }
        for order in package.orders
    ]
    return _write_csv(path, _order_ticket_columns(), rows)


def write_fill_template_csv(package: ManualExecutionPackage, path: Path) -> Path:
    rows = [
        {
            "trade_date": order.trade_date,
            "ts_code": order.ts_code,
            "side": order.side,
            "quantity": "",
            "price": "",
            "amount": "",
            "broker_order_id": order.broker_order_id,
            "order_id": order.order_id,
            "status": "",
            "operator_note": "",
        }
        for order in package.orders
    ]
    return _write_csv(path, _fill_template_columns(), rows)


def render_manual_execution_markdown(package: ManualExecutionPackage) -> str:
    rows = [
        ["Package", package.package_id],
        ["Status", package.status],
        ["Trade Date", package.trade_date],
        ["Strategy", package.strategy_id],
        ["Orders", package.order_count],
        ["Estimated Notional", f"{package.estimated_notional:,.2f}"],
        ["Order Ticket", package.order_ticket_path],
        ["Fill Template", package.fill_template_path],
        ["Broker Submission", package.broker_submission_path],
    ]
    order_rows = [
        [
            order.ts_code,
            order.side,
            order.quantity,
            f"{order.limit_price:.4f}",
            f"{order.estimated_notional:,.2f}",
            order.order_id,
        ]
        for order in package.orders
    ]
    return "\n".join(
        [
            "# Manual Execution Package",
            "",
            _table(["Field", "Value"], rows),
            "",
            "## Order Ticket",
            _table(["Code", "Side", "Qty", "Limit Price", "Notional", "Order ID"], order_rows)
            if order_rows
            else "_No orders._",
            "",
        ]
    )


def _manual_order(raw_order: object) -> ManualExecutionOrder:
    if not isinstance(raw_order, dict):
        raise ValueError("broker submission orders must contain objects")
    quantity = int(raw_order.get("quantity", 0) or 0)
    price = float(raw_order.get("price", 0.0) or 0.0)
    return ManualExecutionOrder(
        broker_order_id=str(raw_order.get("broker_order_id", "")),
        order_id=str(raw_order.get("order_id", "")),
        account_id=str(raw_order.get("account_id", "")),
        strategy_id=str(raw_order.get("strategy_id", "")),
        trade_date=str(raw_order.get("trade_date", "")),
        ts_code=str(raw_order.get("ts_code", "")),
        side=str(raw_order.get("side", "")).upper(),
        quantity=quantity,
        limit_price=price,
        target_weight=float(raw_order.get("target_weight", 0.0) or 0.0),
        estimated_notional=abs(quantity * price),
    )


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _order_ticket_columns() -> list[str]:
    return [
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
    ]


def _fill_template_columns() -> list[str]:
    return [
        "trade_date",
        "ts_code",
        "side",
        "quantity",
        "price",
        "amount",
        "broker_order_id",
        "order_id",
        "status",
        "operator_note",
    ]


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"manual execution input not found: {path}")
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
