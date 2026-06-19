from __future__ import annotations

import json

from quant.apps.risk_guard import ORDER_COLUMNS, load_order_intents, read_control_file, render_control_file


def test_load_order_intents_exports_guard_columns(tmp_path) -> None:
    plan = tmp_path / "paper_plan.json"
    plan.write_text(
        json.dumps(
            {
                "order_intents": [
                    {
                        "order_id": "o1",
                        "account_id": "paper",
                        "strategy_id": "momentum_rank",
                        "ts_code": "000001.SZ",
                        "side": "BUY",
                        "quantity": 100,
                        "price": 10.5,
                        "target_weight": 0.05,
                        "trade_date": "2024-09-09",
                        "extra": "ignored",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    orders = load_order_intents(plan)

    assert list(orders.columns) == ORDER_COLUMNS
    assert orders.iloc[0]["order_id"] == "o1"
    assert orders.iloc[0]["quantity"] == 100
    assert orders.iloc[0]["price"] == 10.5


def test_render_and_read_control_file(tmp_path) -> None:
    control_path = tmp_path / "risk_guard_control.env"
    control_path.write_text(
        render_control_file(
            trade_mode="sell-only",
            max_order_amount=50000.0,
            max_single_weight=0.08,
            max_total_buy_weight=0.5,
            daily_loss=0.03,
            max_daily_loss=0.05,
            trading_start="09:30",
            trading_end="15:00",
            now="10:00",
            reason="test",
            updated_at="2024-09-09T10:00:00+00:00",
        ),
        encoding="utf-8",
    )

    values = read_control_file(control_path)

    assert values["trade_mode"] == "SELL_ONLY"
    assert values["max_order_amount"] == "50000.0"
    assert values["reason"] == "test"
