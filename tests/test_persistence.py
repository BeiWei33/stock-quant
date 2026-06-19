from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.models import (
    Event,
    OrderFill,
    OrderIntent,
    OrderRiskResult,
    RiskDecision,
    StrategyRegistration,
)
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.reconciliation.positions import reconcile_positions
from quant.core.reconciliation.trades import reconcile_trade_activity


def test_sqlite_store_persists_strategy_universe_signals_and_orders(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    store.save_strategy(
        StrategyRegistration(
            strategy_id="momentum_rank",
            strategy_version="v1",
            description="test",
            factor_set_id="technical_momentum_v1",
            code_hash="abc",
            config_hash="cfg",
            config_json='{"strategy_id":"momentum_rank"}',
            status="paper",
        )
    )
    store.save_universe_snapshot(
        "a_share_v1",
        date(2024, 1, 31),
        pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "include_reason": "PASS",
                    "exclude_reason": "",
                    "is_active": True,
                }
            ]
        ),
    )
    store.save_signals(
        pd.DataFrame(
            [
                {
                    "trade_date": date(2024, 1, 31),
                    "ts_code": "000001.SZ",
                    "strategy_id": "momentum_rank",
                    "strategy_version": "v1",
                    "signal_type": "BUY",
                    "score": 1.0,
                    "reason": "test",
                }
            ]
        )
    )
    store.save_order_intents(
        [
            OrderIntent(
                account_id="paper",
                strategy_id="momentum_rank",
                trade_date=date(2024, 1, 31),
                ts_code="000001.SZ",
                side="BUY",
                quantity=100,
                price=10.0,
                target_weight=0.1,
            )
        ]
    )
    store.save_order_risk_results(
        [
            OrderRiskResult(
                order=OrderIntent(
                    account_id="paper",
                    strategy_id="momentum_rank",
                    trade_date=date(2024, 1, 31),
                    ts_code="000001.SZ",
                    side="BUY",
                    quantity=100,
                    price=10.0,
                    target_weight=0.1,
                ),
                decision=RiskDecision.allow(),
            )
        ]
    )

    assert store.count_rows("strategy_registry") == 1
    saved = store.load_strategy("momentum_rank", "v1")
    assert saved is not None
    assert saved.config_hash == "cfg"
    assert saved.config_json == '{"strategy_id":"momentum_rank"}'
    assert store.count_rows("universe_snapshot") == 1
    assert store.count_rows("signal") == 1
    assert store.count_rows("order_intent") == 1
    assert store.count_rows("order_risk_check") == 1


def test_sqlite_store_persists_reconciliation_report(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    report = reconcile_positions(
        account_id="paper",
        trade_date=date(2024, 1, 31),
        local_positions=pd.DataFrame([{"ts_code": "000001.SZ", "quantity": 100}]),
        broker_positions=pd.DataFrame([{"ts_code": "000001.SZ", "quantity": 0}]),
    )

    store.save_reconciliation_report(report)

    assert store.count_rows("reconciliation_report") == 1


def test_sqlite_store_persists_trade_reconciliation_report(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    report = reconcile_trade_activity(
        account_id="paper",
        trade_date=date(2024, 1, 31),
        local_orders=pd.DataFrame([{"ts_code": "000001.SZ", "side": "BUY", "quantity": 100}]),
        broker_orders=pd.DataFrame([{"ts_code": "000001.SZ", "side": "BUY", "quantity": 0}]),
    )

    store.save_trade_reconciliation_report(report)

    assert store.count_rows("reconciliation_report") == 1


def test_sqlite_store_records_order_trace_events(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    order = OrderIntent(
        account_id="paper",
        strategy_id="momentum_rank",
        trade_date=date(2024, 1, 31),
        ts_code="000001.SZ",
        side="BUY",
        quantity=100,
        price=10.0,
        target_weight=0.1,
    )
    fill = OrderFill(
        fill_id=f"{order.order_id}:FILL",
        order_id=order.order_id,
        account_id=order.account_id,
        strategy_id=order.strategy_id,
        ts_code=order.ts_code,
        side=order.side,
        price=10.0,
        quantity=100,
        amount=1000.0,
        fee=5.0,
        tax=0.0,
        trade_date=order.trade_date,
    )

    store.save_order_intents([order])
    store.save_order_risk_results([OrderRiskResult(order=order, decision=RiskDecision.allow())])
    store.save_order_fills([fill])

    trace = store.load_trace(order.order_id)

    assert trace["event_type"].tolist() == [
        "OrderIntentEvent",
        "RiskCheckEvent",
        "TradeEvent",
    ]
    assert trace.iloc[0]["trace_id"] == order.order_id
    assert trace.iloc[0]["payload"]["order_id"] == order.order_id


def test_sqlite_store_persists_custom_events(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()

    store.save_events(
        [
            Event(
                event_type="SystemEvent",
                source="test",
                trace_id="daily:2024-01-31",
                correlation_id="2024-01-31",
                payload={"status": "OK"},
            )
        ]
    )

    events = store.load_events(event_type="SystemEvent", trace_id="daily:2024-01-31")

    assert len(events) == 1
    assert events.iloc[0]["payload"] == {"status": "OK"}
