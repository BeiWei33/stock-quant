from __future__ import annotations

from datetime import date

from quant.apps.events import render_events_markdown
from quant.core.models import OrderIntent, OrderRiskResult, RiskDecision
from quant.core.persistence.sqlite_store import SqliteStore


def test_events_app_renders_trace_markdown(tmp_path) -> None:
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
    store.save_order_intents([order])
    store.save_order_risk_results([OrderRiskResult(order=order, decision=RiskDecision.allow())])

    markdown = render_events_markdown(store.load_trace(order.order_id), "Event Trace")

    assert "OrderIntentEvent" in markdown
    assert "RiskCheckEvent" in markdown
    assert order.order_id in markdown
