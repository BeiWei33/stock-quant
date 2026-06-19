from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.reconciliation.positions import reconcile_positions
from quant.core.reconciliation.trades import reconcile_trade_activity


def test_reconcile_positions_reports_differences() -> None:
    report = reconcile_positions(
        account_id="paper",
        trade_date=date(2024, 1, 31),
        local_positions=pd.DataFrame(
            [{"ts_code": "000001.SZ", "quantity": 100}, {"ts_code": "000002.SZ", "quantity": 200}]
        ),
        broker_positions=pd.DataFrame(
            [{"ts_code": "000001.SZ", "quantity": 100}, {"ts_code": "000002.SZ", "quantity": 100}]
        ),
    )

    assert report.status == "DIFF"
    assert report.differences.iloc[0]["quantity_diff"] == 100


def test_reconcile_trade_activity_reports_order_and_fill_differences() -> None:
    report = reconcile_trade_activity(
        account_id="paper",
        trade_date=date(2024, 1, 31),
        local_orders=pd.DataFrame(
            [
                {"ts_code": "000001.SZ", "side": "BUY", "quantity": 100, "price": 10.0},
                {"ts_code": "000002.SZ", "side": "SELL", "quantity": 200, "price": 8.0},
            ]
        ),
        broker_orders=pd.DataFrame(
            [
                {"ts_code": "000001.SZ", "side": "BUY", "quantity": 100, "price": 10.0},
                {"ts_code": "000002.SZ", "side": "SELL", "quantity": 100, "price": 8.0},
            ]
        ),
        local_fills=pd.DataFrame(
            [{"ts_code": "000001.SZ", "side": "BUY", "quantity": 100, "amount": 1000.0}]
        ),
        broker_fills=pd.DataFrame(
            [{"ts_code": "000001.SZ", "side": "BUY", "quantity": 100, "amount": 999.0}]
        ),
    )

    assert report.status == "DIFF"
    assert report.order_differences.iloc[0]["quantity_diff"] == 100
    assert report.fill_differences.iloc[0]["amount_diff"] == 1.0
    assert report.report_id == "paper:2024-01-31:trades"


def test_reconcile_trade_activity_passes_matching_records() -> None:
    records = pd.DataFrame(
        [{"ts_code": "000001.SZ", "side": "BUY", "quantity": 100, "amount": 1000.0}]
    )

    report = reconcile_trade_activity(
        account_id="paper",
        trade_date=date(2024, 1, 31),
        local_orders=records,
        broker_orders=records,
        local_fills=records,
        broker_fills=records,
    )

    assert report.status == "OK"
    assert report.differences.empty
