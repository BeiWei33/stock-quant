from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant.core.execution.drift_report import build_drift_report


def test_drift_report_breaks_down_directional_slippage_and_costs() -> None:
    trade_date = date(2024, 1, 3)
    orders = pd.DataFrame(
        [
            {
                "order_id": "paper:momentum_rank:2024-01-03:000001.SZ:BUY",
                "account_id": "paper",
                "strategy_id": "momentum_rank",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "price": 10.0,
                "quantity": 100,
                "target_weight": 0.1,
                "trade_date": trade_date,
                "reason": "rebalance",
                "status": "CREATED",
            },
            {
                "order_id": "paper:momentum_rank:2024-01-03:000002.SZ:SELL",
                "account_id": "paper",
                "strategy_id": "momentum_rank",
                "ts_code": "000002.SZ",
                "side": "SELL",
                "price": 20.0,
                "quantity": 200,
                "target_weight": 0.0,
                "trade_date": trade_date,
                "reason": "rebalance",
                "status": "CREATED",
            },
        ]
    )
    fills = pd.DataFrame(
        [
            {
                "fill_id": "buy-fill",
                "order_id": "paper:momentum_rank:2024-01-03:000001.SZ:BUY",
                "account_id": "paper",
                "strategy_id": "momentum_rank",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "price": 10.1,
                "quantity": 100,
                "amount": 1010.0,
                "fee": 5.0,
                "tax": 0.0,
                "trade_date": trade_date,
            },
            {
                "fill_id": "sell-fill",
                "order_id": "paper:momentum_rank:2024-01-03:000002.SZ:SELL",
                "account_id": "paper",
                "strategy_id": "momentum_rank",
                "ts_code": "000002.SZ",
                "side": "SELL",
                "price": 19.8,
                "quantity": 100,
                "amount": 1980.0,
                "fee": 5.0,
                "tax": 1.0,
                "trade_date": trade_date,
            },
        ]
    )

    report = build_drift_report(orders=orders, fills=fills, trade_date=trade_date, account_id="paper")

    assert report.order_count == 2
    assert report.filled_order_count == 2
    assert report.fill_count == 2
    assert report.rejected_count == 0
    assert report.partial_fill_count == 1
    assert report.unfilled_count == 0
    assert report.buy_avg_slippage_bp == pytest.approx(100.0)
    assert report.sell_avg_slippage_bp == pytest.approx(-100.0)
    assert report.commission == 10.0
    assert report.tax == 1.0
    assert report.explicit_cost == 11.0
    assert report.slippage_cost == pytest.approx(30.0)
    assert report.total_execution_cost == pytest.approx(41.0)
    assert report.unfilled_details[0]["unfilled_quantity"] == 100


def test_drift_report_lists_unfilled_orders_without_fills() -> None:
    trade_date = date(2024, 1, 3)
    orders = pd.DataFrame(
        [
            {
                "order_id": "paper:momentum_rank:2024-01-03:000001.SZ:BUY",
                "account_id": "paper",
                "strategy_id": "momentum_rank",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "price": 10.0,
                "quantity": 100,
                "target_weight": 0.1,
                "trade_date": trade_date,
                "reason": "rebalance",
                "status": "CREATED",
            }
        ]
    )

    report = build_drift_report(orders=orders, fills=pd.DataFrame(), trade_date=trade_date, account_id="paper")

    assert report.order_count == 1
    assert report.filled_order_count == 0
    assert report.fill_count == 0
    assert report.unfilled_count == 1
    assert report.unfilled_details == [
        {
            "order_id": "paper:momentum_rank:2024-01-03:000001.SZ:BUY",
            "ts_code": "000001.SZ",
            "side": "BUY",
            "order_quantity": 100,
            "filled_quantity": 0,
            "unfilled_quantity": 100,
            "expected_price": 10.0,
            "status": "CREATED",
        }
    ]
