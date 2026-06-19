from __future__ import annotations

import json

from quant.core.execution.authorization import build_execution_policy, write_execution_policy_json
from quant.core.execution.live_rehearsal import (
    build_live_rehearsal_report,
    render_live_rehearsal_markdown,
    write_live_rehearsal_json,
    write_live_rehearsal_markdown,
)


def test_live_rehearsal_blocks_without_policy(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    _write_dry_run_submission(submission)

    report = build_live_rehearsal_report(broker_submission_path=submission, live_adapter="qmt")

    assert report.status == "EXPECTED_BLOCK"
    assert report.live_adapter == "qmt"
    assert report.default_authorization.mode == "LIVE"
    assert not report.default_authorization.passed
    assert "Live Execution Rehearsal" in render_live_rehearsal_markdown(report)


def test_live_rehearsal_passes_with_matching_live_policy(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    policy_path = tmp_path / "execution_policy.json"
    _write_dry_run_submission(submission)
    policy = build_execution_policy(
        mode="LIVE",
        adapter="qmt",
        trade_date="2024-09-09",
        strategy_id="momentum_rank",
        approval_id="approval-1",
        approved_by="operator",
        expires_at="2099-09-09T15:00:00+00:00",
        max_order_count=2,
        max_notional=2000,
    )
    write_execution_policy_json(policy, policy_path)

    report = build_live_rehearsal_report(
        broker_submission_path=submission,
        live_adapter="qmt",
        policy_path=policy_path,
    )

    assert report.status == "PASS"
    assert report.policy_authorization is not None
    assert report.policy_authorization.passed


def test_live_rehearsal_writers_emit_json_and_markdown(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    _write_dry_run_submission(submission)
    report = build_live_rehearsal_report(broker_submission_path=submission)

    json_path = write_live_rehearsal_json(report, tmp_path / "live_rehearsal.json")
    markdown_path = write_live_rehearsal_markdown(report, tmp_path / "live_rehearsal.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "EXPECTED_BLOCK"
    assert "EXPECTED_BLOCK" in markdown_path.read_text(encoding="utf-8")


def _write_dry_run_submission(path) -> None:
    path.write_text(
        json.dumps(
            {
                "mode": "DRY_RUN",
                "adapter": "dry_run",
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "risk_guard_allowed": True,
                "order_count": 1,
                "orders": [
                    {
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
