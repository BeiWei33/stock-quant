from __future__ import annotations

import json

import pytest

from quant.core.execution.broker import build_dry_run_submission, render_submission_markdown


def test_build_dry_run_submission_requires_risk_guard_allow(tmp_path) -> None:
    plan = tmp_path / "paper_plan.json"
    risk_guard = tmp_path / "risk_guard.json"
    plan.write_text(json.dumps({"trade_date": "2024-09-09", "order_intents": []}), encoding="utf-8")
    risk_guard.write_text(json.dumps({"allowed": False, "rejected_orders": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="risk guard did not allow"):
        build_dry_run_submission(plan_path=plan, risk_guard_report_path=risk_guard)


def test_build_dry_run_submission_packages_orders(tmp_path) -> None:
    plan = tmp_path / "paper_plan.json"
    risk_guard = tmp_path / "risk_guard.json"
    plan.write_text(
        json.dumps(
            {
                "trade_date": "2024-09-09",
                "strategy": {"strategy_id": "momentum_rank"},
                "order_intents": [
                    {
                        "order_id": "paper:momentum_rank:2024-09-09:000001.SZ:BUY",
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
    risk_guard.write_text(json.dumps({"allowed": True, "rejected_orders": 0}), encoding="utf-8")

    package = build_dry_run_submission(plan_path=plan, risk_guard_report_path=risk_guard)

    assert package.mode == "DRY_RUN"
    assert package.strategy_id == "momentum_rank"
    assert package.order_count == 1
    assert package.orders[0].broker_order_id.startswith("DRYRUN:")
    assert package.orders[0].status == "DRY_RUN_ACCEPTED"
    assert "Broker Submission Package" in render_submission_markdown(package)
