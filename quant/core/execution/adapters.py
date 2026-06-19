from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from quant.core.execution.authorization import ExecutionAuthorizationReport


@dataclass(frozen=True)
class BrokerAdapterOrderResult:
    order_id: str
    broker_order_id: str
    ts_code: str
    side: str
    quantity: int
    price: float
    status: str
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BrokerAdapterSubmissionResult:
    submission_id: str
    adapter: str
    mode: str
    status: str
    accepted_count: int
    rejected_count: int
    orders: list[BrokerAdapterOrderResult]

    @property
    def passed(self) -> bool:
        return self.status == "ACCEPTED" and self.rejected_count == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "submission_id": self.submission_id,
            "adapter": self.adapter,
            "mode": self.mode,
            "status": self.status,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "orders": [order.to_dict() for order in self.orders],
        }


@dataclass(frozen=True)
class BrokerAdapterContractReport:
    status: str
    passed: bool
    adapter: str
    mode: str
    submission_id: str
    trade_date: str
    strategy_id: str
    order_count: int
    submitted: bool
    issue: str
    result: BrokerAdapterSubmissionResult | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed": self.passed,
            "adapter": self.adapter,
            "mode": self.mode,
            "submission_id": self.submission_id,
            "trade_date": self.trade_date,
            "strategy_id": self.strategy_id,
            "order_count": self.order_count,
            "submitted": self.submitted,
            "issue": self.issue,
            "result": self.result.to_dict() if self.result is not None else None,
        }


class BrokerAdapter(Protocol):
    adapter_id: str
    supported_modes: tuple[str, ...]

    def submit(self, submission: dict[str, Any]) -> BrokerAdapterSubmissionResult:
        """Submit an already validated broker submission package."""


class DryRunBrokerAdapter:
    adapter_id = "dry_run"
    supported_modes = ("DRY_RUN",)

    def submit(self, submission: dict[str, Any]) -> BrokerAdapterSubmissionResult:
        orders = [
            BrokerAdapterOrderResult(
                order_id=str(order["order_id"]),
                broker_order_id=str(order["broker_order_id"]),
                ts_code=str(order["ts_code"]),
                side=str(order["side"]).upper(),
                quantity=int(order["quantity"]),
                price=float(order["price"]),
                status="DRY_RUN_ACCEPTED",
                message="accepted by dry-run adapter",
            )
            for order in submission.get("orders", [])
            if isinstance(order, dict)
        ]
        return BrokerAdapterSubmissionResult(
            submission_id=str(submission.get("submission_id", uuid4().hex)),
            adapter=self.adapter_id,
            mode="DRY_RUN",
            status="ACCEPTED",
            accepted_count=len(orders),
            rejected_count=0,
            orders=orders,
        )


class QmtBrokerAdapterSkeleton:
    adapter_id = "qmt"
    supported_modes = ("LIVE",)

    def submit(self, submission: dict[str, Any]) -> BrokerAdapterSubmissionResult:
        raise NotImplementedError("QMT broker adapter is not configured in this environment")


def submit_with_contract(
    *,
    adapter: BrokerAdapter,
    submission: dict[str, Any],
    authorization: ExecutionAuthorizationReport | dict[str, Any],
) -> BrokerAdapterSubmissionResult:
    validate_broker_adapter_contract(
        adapter=adapter,
        submission=submission,
        authorization=authorization,
    )
    result = adapter.submit(submission)
    _validate_adapter_result(adapter=adapter, submission=submission, result=result)
    return result


def build_broker_adapter_contract_report(
    *,
    adapter: BrokerAdapter,
    submission: dict[str, Any],
    authorization: ExecutionAuthorizationReport | dict[str, Any],
    submit: bool = False,
) -> BrokerAdapterContractReport:
    result = None
    issue = ""
    try:
        if submit:
            result = submit_with_contract(
                adapter=adapter,
                submission=submission,
                authorization=authorization,
            )
        else:
            validate_broker_adapter_contract(
                adapter=adapter,
                submission=submission,
                authorization=authorization,
            )
    except Exception as exc:
        issue = str(exc)
    passed = issue == "" and (result.passed if result is not None else True)
    return BrokerAdapterContractReport(
        status="OK" if passed else "ERROR",
        passed=passed,
        adapter=adapter.adapter_id,
        mode=str(submission.get("mode", "")).upper(),
        submission_id=str(submission.get("submission_id", "")),
        trade_date=str(submission.get("trade_date", "")),
        strategy_id=str(submission.get("strategy_id", "")),
        order_count=int(submission.get("order_count", 0) or 0),
        submitted=submit and result is not None,
        issue=issue,
        result=result,
    )


def write_broker_adapter_contract_json(report: BrokerAdapterContractReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_broker_adapter_contract_markdown(report: BrokerAdapterContractReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_broker_adapter_contract_markdown(report), encoding="utf-8")
    return path


def render_broker_adapter_contract_markdown(report: BrokerAdapterContractReport) -> str:
    rows = [
        ["Status", report.status],
        ["Passed", report.passed],
        ["Adapter", report.adapter],
        ["Mode", report.mode],
        ["Submission", report.submission_id or "-"],
        ["Trade Date", report.trade_date or "-"],
        ["Strategy", report.strategy_id or "-"],
        ["Orders", report.order_count],
        ["Submitted", report.submitted],
        ["Issue", report.issue or "-"],
    ]
    result_rows = []
    if report.result is not None:
        result_rows = [
            [
                order.order_id,
                order.broker_order_id,
                order.ts_code,
                order.side,
                order.quantity,
                f"{order.price:.4f}",
                order.status,
            ]
            for order in report.result.orders
        ]
    return "\n".join(
        [
            "# Broker Adapter Contract",
            "",
            _table(["Field", "Value"], rows),
            "",
            "## Result Orders",
            _table(["Order", "Broker Order", "Code", "Side", "Qty", "Price", "Status"], result_rows)
            if result_rows
            else "_No submission was sent._",
            "",
        ]
    )


def validate_broker_adapter_contract(
    *,
    adapter: BrokerAdapter,
    submission: dict[str, Any],
    authorization: ExecutionAuthorizationReport | dict[str, Any],
) -> None:
    auth = _authorization_dict(authorization)
    if not bool(auth.get("passed", False)):
        raise ValueError("broker adapter contract requires passed execution authorization")
    mode = str(submission.get("mode", "")).upper()
    adapter_id = str(submission.get("adapter", ""))
    if adapter_id != adapter.adapter_id:
        raise ValueError(f"submission adapter {adapter_id or 'UNKNOWN'} does not match adapter {adapter.adapter_id}")
    if mode not in adapter.supported_modes:
        raise ValueError(f"adapter {adapter.adapter_id} does not support mode {mode or 'UNKNOWN'}")
    if str(auth.get("mode", "")).upper() != mode:
        raise ValueError("authorization mode does not match submission mode")
    if str(auth.get("adapter", "")) != adapter_id:
        raise ValueError("authorization adapter does not match submission adapter")
    if str(auth.get("trade_date", "")) != str(submission.get("trade_date", "")):
        raise ValueError("authorization trade_date does not match submission")
    if str(auth.get("strategy_id", "")) != str(submission.get("strategy_id", "")):
        raise ValueError("authorization strategy_id does not match submission")
    if int(auth.get("order_count", 0) or 0) != int(submission.get("order_count", 0) or 0):
        raise ValueError("authorization order_count does not match submission")
    if not bool(submission.get("risk_guard_allowed", False)):
        raise ValueError("broker adapter contract requires risk_guard_allowed=true")
    orders = submission.get("orders", [])
    if not isinstance(orders, list):
        raise ValueError("broker submission orders must be a list")
    if len(orders) != int(submission.get("order_count", 0) or 0):
        raise ValueError("broker submission order_count does not match orders length")
    _validate_orders(orders, mode=mode, adapter_id=adapter_id)


def _validate_orders(orders: list[object], *, mode: str, adapter_id: str) -> None:
    seen_order_ids: set[str] = set()
    seen_broker_order_ids: set[str] = set()
    required = {
        "broker_order_id",
        "order_id",
        "account_id",
        "strategy_id",
        "ts_code",
        "side",
        "quantity",
        "price",
        "trade_date",
    }
    for index, raw_order in enumerate(orders, start=1):
        if not isinstance(raw_order, dict):
            raise ValueError(f"broker submission order #{index} must be an object")
        missing = sorted(required - set(raw_order.keys()))
        if missing:
            raise ValueError(f"broker submission order #{index} missing fields: {','.join(missing)}")
        order_id = str(raw_order.get("order_id", ""))
        broker_order_id = str(raw_order.get("broker_order_id", ""))
        if not order_id or order_id in seen_order_ids:
            raise ValueError(f"broker submission order #{index} has duplicate or empty order_id")
        if not broker_order_id or broker_order_id in seen_broker_order_ids:
            raise ValueError(f"broker submission order #{index} has duplicate or empty broker_order_id")
        seen_order_ids.add(order_id)
        seen_broker_order_ids.add(broker_order_id)
        if mode == "LIVE" and broker_order_id.upper().startswith("DRYRUN:"):
            raise ValueError("LIVE broker submission cannot use DRYRUN broker_order_id")
        if raw_order.get("adapter") is not None and str(raw_order.get("adapter")) != adapter_id:
            raise ValueError(f"broker submission order #{index} adapter does not match package adapter")
        side = str(raw_order.get("side", "")).upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError(f"broker submission order #{index} has unsupported side={side or 'UNKNOWN'}")
        if int(raw_order.get("quantity", 0) or 0) <= 0:
            raise ValueError(f"broker submission order #{index} quantity must be positive")
        if float(raw_order.get("price", 0.0) or 0.0) <= 0:
            raise ValueError(f"broker submission order #{index} price must be positive")


def _validate_adapter_result(
    *,
    adapter: BrokerAdapter,
    submission: dict[str, Any],
    result: BrokerAdapterSubmissionResult,
) -> None:
    if result.adapter != adapter.adapter_id:
        raise ValueError("adapter result adapter does not match adapter id")
    if result.mode != str(submission.get("mode", "")).upper():
        raise ValueError("adapter result mode does not match submission mode")
    if result.accepted_count + result.rejected_count != int(submission.get("order_count", 0) or 0):
        raise ValueError("adapter result counts do not match submission order_count")


def _authorization_dict(authorization: ExecutionAuthorizationReport | dict[str, Any]) -> dict[str, Any]:
    if isinstance(authorization, ExecutionAuthorizationReport):
        return authorization.to_dict()
    return authorization


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
