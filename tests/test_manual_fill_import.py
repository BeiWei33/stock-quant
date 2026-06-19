from __future__ import annotations

import json

import pandas as pd

from quant.core.execution.fill_import import (
    import_manual_fills,
    load_fill_column_mapping,
    render_manual_fill_import_markdown,
    write_manual_fill_import_json,
    write_manual_fill_import_markdown,
)
from quant.core.execution.manual_reconcile import build_manual_reconciliation, validate_manual_fills


def test_manual_fill_import_writes_valid_full_fill_template(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    source = tmp_path / "broker_fills.csv"
    output = tmp_path / "manual_fill_template.csv"
    _write_order_ticket(order_ticket)
    pd.DataFrame(
        [
            {
                "broker_order_id": "DRYRUN:order-1",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "quantity": "100",
                "price": "10.50",
                "status": "FILLED",
            }
        ]
    ).to_csv(source, index=False)

    report = import_manual_fills(
        order_ticket_path=order_ticket,
        broker_fills_path=source,
        output_path=output,
    )

    assert report.status == "OK"
    assert report.passed
    assert report.imported_count == 1
    assert "Manual Fill Import" in render_manual_fill_import_markdown(report)
    validation = validate_manual_fills(order_ticket_path=order_ticket, fill_template_path=output)
    assert validation.passed
    bundle = build_manual_reconciliation(
        order_ticket_path=order_ticket,
        fill_template_path=output,
        trade_date=pd.to_datetime("2024-09-09").date(),
        output_dir=tmp_path,
    )
    assert bundle.reconciliation.status == "OK"


def test_manual_fill_import_aggregates_partial_fills(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    source = tmp_path / "broker_fills.csv"
    output = tmp_path / "manual_fill_template.csv"
    _write_order_ticket(order_ticket)
    pd.DataFrame(
        [
            {"order_id": "order-1", "quantity": "30", "price": "10.00", "status": "FILLED"},
            {"order_id": "order-1", "quantity": "20", "price": "11.00", "status": "FILLED"},
        ]
    ).to_csv(source, index=False)

    report = import_manual_fills(
        order_ticket_path=order_ticket,
        broker_fills_path=source,
        output_path=output,
    )

    row = pd.read_csv(output, dtype=str).iloc[0]
    assert report.status == "OK"
    assert report.matched_count == 2
    assert row["status"] == "PARTIAL_FILLED"
    assert row["quantity"] == "50"
    assert row["amount"] == "520.00"
    validation = validate_manual_fills(order_ticket_path=order_ticket, fill_template_path=output)
    assert validation.passed
    bundle = build_manual_reconciliation(
        order_ticket_path=order_ticket,
        fill_template_path=output,
        trade_date=pd.to_datetime("2024-09-09").date(),
        output_dir=tmp_path,
    )
    assert bundle.reconciliation.status == "DIFF"


def test_manual_fill_import_reports_overfill(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    source = tmp_path / "broker_fills.csv"
    output = tmp_path / "manual_fill_template.csv"
    _write_order_ticket(order_ticket)
    pd.DataFrame(
        [
            {
                "broker_order_id": "DRYRUN:order-1",
                "quantity": "150",
                "price": "10.50",
                "status": "FILLED",
            }
        ]
    ).to_csv(source, index=False)

    report = import_manual_fills(
        order_ticket_path=order_ticket,
        broker_fills_path=source,
        output_path=output,
    )

    assert report.status == "ERROR"
    assert not report.passed
    assert any(issue.field == "quantity" for issue in report.issues)
    json_path = write_manual_fill_import_json(report, tmp_path / "fill_import.json")
    md_path = write_manual_fill_import_markdown(report, tmp_path / "fill_import.md")
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "ERROR"
    assert "Manual Fill Import" in md_path.read_text(encoding="utf-8")


def test_manual_fill_import_uses_configured_column_mapping(tmp_path) -> None:
    order_ticket = tmp_path / "manual_order_ticket.csv"
    source = tmp_path / "broker_fills.csv"
    output = tmp_path / "manual_fill_template.csv"
    mapping = tmp_path / "fill_import.yaml"
    _write_order_ticket(order_ticket)
    pd.DataFrame(
        [
            {
                "券商订单号": "DRYRUN:order-1",
                "证券代码": "000001.SZ",
                "买卖方向": "BUY",
                "成交数量": "100",
                "成交价格": "10.50",
                "成交状态": "FILLED",
            }
        ]
    ).to_csv(source, index=False)
    mapping.write_text(
        "\n".join(
            [
                "columns:",
                "  broker_order_id: [券商订单号]",
                "  ts_code: [证券代码]",
                "  side: [买卖方向]",
                "  quantity: [成交数量]",
                "  price: [成交价格]",
                "  status: [成交状态]",
            ]
        ),
        encoding="utf-8",
    )

    report = import_manual_fills(
        order_ticket_path=order_ticket,
        broker_fills_path=source,
        output_path=output,
        column_mapping=load_fill_column_mapping(mapping),
    )

    assert report.status == "OK"
    row = pd.read_csv(output, dtype=str).iloc[0]
    assert row["quantity"] == "100"
    assert row["price"] == "10.5000"


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
