from __future__ import annotations

import pytest

from quant.core.execution.adapters import (
    BrokerAdapterSubmissionResult,
    DryRunBrokerAdapter,
    QmtBrokerAdapterSkeleton,
    build_broker_adapter_contract_report,
    render_broker_adapter_contract_markdown,
    submit_with_contract,
    validate_broker_adapter_contract,
)


def test_dry_run_adapter_accepts_authorized_submission() -> None:
    submission = _submission()
    result = submit_with_contract(
        adapter=DryRunBrokerAdapter(),
        submission=submission,
        authorization=_authorization(),
    )

    assert result.passed
    assert result.adapter == "dry_run"
    assert result.mode == "DRY_RUN"
    assert result.accepted_count == 1
    assert result.orders[0].status == "DRY_RUN_ACCEPTED"


def test_adapter_contract_blocks_failed_authorization() -> None:
    authorization = _authorization(passed=False, status="BLOCK")

    with pytest.raises(ValueError, match="passed execution authorization"):
        submit_with_contract(
            adapter=DryRunBrokerAdapter(),
            submission=_submission(),
            authorization=authorization,
        )


def test_adapter_contract_blocks_authorization_mismatch() -> None:
    authorization = _authorization(order_count=2)

    with pytest.raises(ValueError, match="order_count"):
        submit_with_contract(
            adapter=DryRunBrokerAdapter(),
            submission=_submission(),
            authorization=authorization,
        )


def test_adapter_contract_blocks_live_dryrun_order_ids() -> None:
    submission = _submission(mode="LIVE", adapter="qmt")
    authorization = _authorization(mode="LIVE", adapter="qmt")

    with pytest.raises(ValueError, match="DRYRUN"):
        validate_broker_adapter_contract(
            adapter=QmtBrokerAdapterSkeleton(),
            submission=submission,
            authorization=authorization,
        )


def test_adapter_contract_blocks_duplicate_order_ids() -> None:
    submission = _submission()
    submission["orders"].append(dict(submission["orders"][0], broker_order_id="DRYRUN:order-2"))
    submission["order_count"] = 2
    authorization = _authorization(order_count=2)

    with pytest.raises(ValueError, match="duplicate or empty order_id"):
        validate_broker_adapter_contract(
            adapter=DryRunBrokerAdapter(),
            submission=submission,
            authorization=authorization,
        )


def test_adapter_contract_validates_adapter_result_counts() -> None:
    class BadCountAdapter:
        adapter_id = "dry_run"
        supported_modes = ("DRY_RUN",)

        def submit(self, submission):
            return BrokerAdapterSubmissionResult(
                submission_id="bad",
                adapter="dry_run",
                mode="DRY_RUN",
                status="ACCEPTED",
                accepted_count=0,
                rejected_count=0,
                orders=[],
            )

    with pytest.raises(ValueError, match="result counts"):
        submit_with_contract(
            adapter=BadCountAdapter(),
            submission=_submission(),
            authorization=_authorization(),
        )


def test_qmt_skeleton_is_explicitly_unconfigured() -> None:
    with pytest.raises(NotImplementedError, match="not configured"):
        QmtBrokerAdapterSkeleton().submit(_submission(mode="LIVE", adapter="qmt", broker_order_id="QMT:order-1"))


def test_adapter_contract_report_captures_contract_error() -> None:
    report = build_broker_adapter_contract_report(
        adapter=DryRunBrokerAdapter(),
        submission=_submission(),
        authorization=_authorization(passed=False, status="BLOCK"),
    )

    assert report.status == "ERROR"
    assert not report.passed
    assert "passed execution authorization" in report.issue
    assert "Broker Adapter Contract" in render_broker_adapter_contract_markdown(report)


def _submission(
    *,
    mode: str = "DRY_RUN",
    adapter: str = "dry_run",
    broker_order_id: str = "DRYRUN:order-1",
) -> dict[str, object]:
    return {
        "submission_id": "submission-1",
        "adapter": adapter,
        "mode": mode,
        "trade_date": "2024-09-09",
        "strategy_id": "momentum_rank",
        "risk_guard_allowed": True,
        "risk_guard_report_path": "risk_guard.json",
        "order_count": 1,
        "orders": [
            {
                "broker_order_id": broker_order_id,
                "order_id": "order-1",
                "account_id": "paper",
                "strategy_id": "momentum_rank",
                "ts_code": "000001.SZ",
                "side": "BUY",
                "quantity": 100,
                "price": 10.5,
                "target_weight": 0.05,
                "trade_date": "2024-09-09",
                "status": "DRY_RUN_ACCEPTED",
                "adapter": adapter,
            }
        ],
    }


def _authorization(
    *,
    passed: bool = True,
    status: str = "GO",
    mode: str = "DRY_RUN",
    adapter: str = "dry_run",
    order_count: int = 1,
) -> dict[str, object]:
    return {
        "status": status,
        "passed": passed,
        "mode": mode,
        "adapter": adapter,
        "trade_date": "2024-09-09",
        "strategy_id": "momentum_rank",
        "order_count": order_count,
        "notional": 1050.0,
        "policy_path": "policy.json",
        "checks": [],
    }
