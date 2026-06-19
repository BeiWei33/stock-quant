from __future__ import annotations

import csv
import json

import pytest

from quant.core.execution.manual import (
    build_manual_execution_package,
    render_manual_execution_markdown,
)


def test_manual_execution_package_writes_ticket_and_fill_template(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    order_ticket = tmp_path / "manual_order_ticket.csv"
    fill_template = tmp_path / "manual_fill_template.csv"
    _write_submission(submission)

    package = build_manual_execution_package(
        broker_submission_path=submission,
        order_ticket_path=order_ticket,
        fill_template_path=fill_template,
    )

    assert package.status == "READY"
    assert package.order_count == 1
    assert package.estimated_notional == 1050.0
    assert "Manual Execution Package" in render_manual_execution_markdown(package)
    ticket_rows = _read_csv(order_ticket)
    fill_rows = _read_csv(fill_template)
    assert ticket_rows[0]["manual_status"] == "PENDING"
    assert ticket_rows[0]["ts_code"] == "000001.SZ"
    assert ticket_rows[0]["estimated_notional"] == "1050.00"
    assert fill_rows[0]["quantity"] == ""
    assert fill_rows[0]["price"] == ""
    assert fill_rows[0]["broker_order_id"] == "DRYRUN:order-1"


def test_manual_execution_package_requires_dry_run_submission(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    _write_submission(submission, mode="LIVE")

    with pytest.raises(ValueError, match="dry-run"):
        build_manual_execution_package(
            broker_submission_path=submission,
            order_ticket_path=tmp_path / "ticket.csv",
            fill_template_path=tmp_path / "fills.csv",
        )


def test_manual_execution_package_requires_risk_guard_link(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    _write_submission(submission, risk_guard_allowed=False)

    with pytest.raises(ValueError, match="risk_guard_allowed"):
        build_manual_execution_package(
            broker_submission_path=submission,
            order_ticket_path=tmp_path / "ticket.csv",
            fill_template_path=tmp_path / "fills.csv",
        )


def _write_submission(path, *, mode: str = "DRY_RUN", risk_guard_allowed: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "mode": mode,
                "adapter": "dry_run",
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "risk_guard_allowed": risk_guard_allowed,
                "order_count": 1,
                "orders": [
                    {
                        "broker_order_id": "DRYRUN:order-1",
                        "order_id": "order-1",
                        "account_id": "paper",
                        "strategy_id": "momentum_rank",
                        "ts_code": "000001.SZ",
                        "side": "BUY",
                        "quantity": 100,
                        "price": 10.5,
                        "target_weight": 0.05,
                        "trade_date": "2024-09-09",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
