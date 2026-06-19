from __future__ import annotations

import pandas as pd
import pytest

from quant.core.execution.manual_reconcile import (
    build_manual_reconciliation,
    render_manual_reconciliation_markdown,
    render_manual_validation_markdown,
    validate_manual_fills,
)


def test_manual_fill_validation_blocks_blank_strict_template(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    fills = tmp_path / "manual_fill_template.csv"
    _write_order_ticket(order_ticket)
    _write_fills(fills, quantity="", price="", amount="", status="")

    report = validate_manual_fills(order_ticket_path=order_ticket, fill_template_path=fills)

    assert not report.passed
    assert report.status == "ERROR"
    assert any(issue.field == "status" for issue in report.issues)
    assert "Manual Fill Validation" in render_manual_validation_markdown(report)


def test_manual_reconciliation_passes_full_matching_fill(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    fills = tmp_path / "manual_fill_template.csv"
    _write_order_ticket(order_ticket)
    _write_fills(fills, quantity="100", price="10.50", amount="1050.00", status="FILLED")

    bundle = build_manual_reconciliation(
        order_ticket_path=order_ticket,
        fill_template_path=fills,
        trade_date=pd.to_datetime("2024-09-09").date(),
        output_dir=tmp_path,
    )

    assert bundle.validation.passed
    assert bundle.reconciliation.status == "OK"
    assert (tmp_path / "manual_local_orders.csv").exists()
    assert (tmp_path / "manual_broker_orders.csv").exists()
    assert (tmp_path / "manual_broker_fills.csv").exists()
    assert "Manual Execution Reconciliation" in render_manual_reconciliation_markdown(bundle)


def test_manual_reconciliation_reports_partial_fill_difference(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    fills = tmp_path / "manual_fill_template.csv"
    _write_order_ticket(order_ticket)
    _write_fills(fills, quantity="50", price="10.50", amount="525.00", status="PARTIAL_FILLED")

    bundle = build_manual_reconciliation(
        order_ticket_path=order_ticket,
        fill_template_path=fills,
        trade_date=pd.to_datetime("2024-09-09").date(),
        output_dir=tmp_path,
    )

    assert bundle.validation.passed
    assert bundle.reconciliation.status == "DIFF"
    assert bundle.reconciliation.fill_differences.iloc[0]["quantity_diff"] == 50


def test_manual_reconciliation_rejects_invalid_amount(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    fills = tmp_path / "manual_fill_template.csv"
    _write_order_ticket(order_ticket)
    _write_fills(fills, quantity="100", price="10.50", amount="100.00", status="FILLED")

    with pytest.raises(ValueError, match="manual fill validation failed"):
        build_manual_reconciliation(
            order_ticket_path=order_ticket,
            fill_template_path=fills,
            trade_date=pd.to_datetime("2024-09-09").date(),
            output_dir=tmp_path,
        )


def _write_order_ticket(path) -> None:
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "quantity": "100",
                "limit_price": "10.50",
                "estimated_notional": "1050.00",
                "account_id": "paper",
                "strategy_id": "momentum_rank",
                "order_id": "order-1",
                "broker_order_id": "DRYRUN:order-1",
                "manual_status": "PENDING",
                "submitted_quantity": "",
                "submitted_price": "",
                "operator_note": "",
            }
        ]
    ).to_csv(path, index=False)


def _write_fills(path, *, quantity: str, price: str, amount: str, status: str) -> None:
    pd.DataFrame(
        [
            {
                "trade_date": "2024-09-09",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "quantity": quantity,
                "price": price,
                "amount": amount,
                "broker_order_id": "DRYRUN:order-1",
                "order_id": "order-1",
                "status": status,
                "operator_note": "",
            }
        ]
    ).to_csv(path, index=False)
