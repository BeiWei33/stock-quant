from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    event_type: str
    source: str
    payload: dict[str, Any]
    trace_id: str = ""
    correlation_id: str = ""
    event_id: str = field(default_factory=lambda: uuid4().hex)
    event_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    receive_time: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_time"] = self.event_time.isoformat()
        data["receive_time"] = self.receive_time.isoformat()
        return data


@dataclass(frozen=True)
class OrderIntent:
    ts_code: str
    side: str
    quantity: int
    price: float
    target_weight: float
    strategy_id: str
    trade_date: date
    account_id: str = "paper"
    reason: str = ""
    status: str = "CREATED"

    @property
    def order_id(self) -> str:
        return f"{self.account_id}:{self.strategy_id}:{self.trade_date.isoformat()}:{self.ts_code}:{self.side}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trade_date"] = self.trade_date.isoformat()
        data["order_id"] = self.order_id
        return data


@dataclass(frozen=True)
class OrderFill:
    fill_id: str
    order_id: str
    account_id: str
    strategy_id: str
    ts_code: str
    side: str
    price: float
    quantity: int
    amount: float
    fee: float
    tax: float
    trade_date: date

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trade_date"] = self.trade_date.isoformat()
        return data


@dataclass(frozen=True)
class OrderRiskResult:
    order: OrderIntent
    decision: RiskDecision

    def to_dict(self) -> dict[str, Any]:
        data = self.order.to_dict()
        data["allowed"] = self.decision.allowed
        data["risk_reasons"] = list(self.decision.reasons)
        return data


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()

    @classmethod
    def allow(cls) -> "RiskDecision":
        return cls(True, ())

    @classmethod
    def reject(cls, *reasons: str) -> "RiskDecision":
        return cls(False, tuple(reason for reason in reasons if reason))


@dataclass(frozen=True)
class PortfolioSnapshot:
    account_id: str
    trade_date: date
    total_asset: float
    cash: float
    market_value: float
    total_position_ratio: float
    daily_return: float
    cum_return: float
    drawdown: float
    benchmark_return: float = 0.0
    excess_return: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trade_date"] = self.trade_date.isoformat()
        return data


@dataclass(frozen=True)
class StrategyRegistration:
    strategy_id: str
    strategy_version: str
    description: str
    factor_set_id: str
    code_hash: str
    config_hash: str = ""
    config_json: str = ""
    research_report_path: str = ""
    status: str = "research"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyAdmissionDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()

    @classmethod
    def allow(cls) -> "StrategyAdmissionDecision":
        return cls(True, ())

    @classmethod
    def reject(cls, *reasons: str) -> "StrategyAdmissionDecision":
        return cls(False, tuple(reason for reason in reasons if reason))


@dataclass(frozen=True)
class WorkflowRun:
    run_id: str
    workflow_name: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    trade_date: date | None = None
    summary_path: str = ""
    error_msg: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["ended_at"] = self.ended_at.isoformat() if self.ended_at else None
        data["trade_date"] = self.trade_date.isoformat() if self.trade_date else None
        return data


@dataclass(frozen=True)
class WorkflowLock:
    workflow_name: str
    run_id: str
    acquired_at: datetime
    expires_at: datetime

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["acquired_at"] = self.acquired_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat()
        return data
