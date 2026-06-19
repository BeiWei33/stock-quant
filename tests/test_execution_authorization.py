from __future__ import annotations

import json
from datetime import UTC, datetime

from quant.core.execution.authorization import (
    build_execution_policy,
    build_execution_authorization_report,
    render_execution_policy_markdown,
    write_execution_policy_json,
    write_execution_policy_markdown,
    render_execution_authorization_markdown,
)


def test_authorization_allows_dry_run_without_policy(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    _write_submission(submission, mode="DRY_RUN", adapter="dry_run")

    report = build_execution_authorization_report(broker_submission_path=submission)

    assert report.passed
    assert report.status == "GO"
    assert report.notional == 1050.0
    assert "Execution Authorization Report" in render_execution_authorization_markdown(report)


def test_authorization_blocks_live_without_policy(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    _write_submission(submission, mode="LIVE", adapter="qmt")

    report = build_execution_authorization_report(broker_submission_path=submission)

    assert not report.passed
    assert report.status == "BLOCK"
    assert any(check.name == "execution_mode_allowed" and not check.passed for check in report.checks)
    assert any(check.name == "auto_trade_enabled" and not check.passed for check in report.checks)


def test_authorization_allows_live_with_matching_policy(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    policy = tmp_path / "execution_policy.json"
    _write_submission(submission, mode="LIVE", adapter="qmt")
    policy.write_text(
        json.dumps(
            {
                "auto_trade_enabled": True,
                "allowed_modes": ["LIVE"],
                "allowed_adapters": ["qmt"],
                "approved_trade_date": "2024-09-09",
                "approved_strategy_id": "momentum_rank",
                "approval_id": "approval-1",
                "approved_by": "operator",
                "expires_at": "2024-09-09T15:00:00+00:00",
                "max_order_count": 2,
                "max_notional": 2000,
            }
        ),
        encoding="utf-8",
    )

    report = build_execution_authorization_report(
        broker_submission_path=submission,
        policy_path=policy,
        now=datetime(2024, 9, 9, 14, 0, tzinfo=UTC),
    )

    assert report.passed
    assert report.status == "GO"


def test_authorization_blocks_expired_or_oversized_policy(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    policy = tmp_path / "execution_policy.json"
    _write_submission(submission, mode="LIVE", adapter="qmt")
    policy.write_text(
        json.dumps(
            {
                "auto_trade_enabled": True,
                "allowed_modes": ["LIVE"],
                "allowed_adapters": ["qmt"],
                "approved_trade_date": "2024-09-09",
                "approved_strategy_id": "momentum_rank",
                "approval_id": "approval-1",
                "approved_by": "operator",
                "expires_at": "2024-09-09T13:00:00+00:00",
                "max_order_count": 2,
                "max_notional": 100,
            }
        ),
        encoding="utf-8",
    )

    report = build_execution_authorization_report(
        broker_submission_path=submission,
        policy_path=policy,
        now=datetime(2024, 9, 9, 14, 0, tzinfo=UTC),
    )

    assert not report.passed
    assert any(check.name == "manual_approval_not_expired" and not check.passed for check in report.checks)
    assert any(check.name == "notional_limit" and not check.passed for check in report.checks)


def test_build_execution_policy_defaults_to_dry_run(tmp_path) -> None:
    policy = build_execution_policy()

    assert not policy.auto_trade_enabled
    assert policy.allowed_modes == ("DRY_RUN",)
    assert policy.allowed_adapters == ("dry_run",)
    assert "Execution Policy" in render_execution_policy_markdown(policy)
    json_path = write_execution_policy_json(policy, tmp_path / "policy.json")
    markdown_path = write_execution_policy_markdown(policy, tmp_path / "policy.md")
    assert json.loads(json_path.read_text(encoding="utf-8"))["allowed_modes"] == ["DRY_RUN"]
    assert "DRY_RUN" in markdown_path.read_text(encoding="utf-8")


def test_build_execution_policy_requires_live_approval_scope() -> None:
    try:
        build_execution_policy(mode="LIVE", adapter="qmt")
    except ValueError as exc:
        assert "trade_date" in str(exc)
        assert "approved_by" in str(exc)
    else:
        raise AssertionError("expected live policy validation error")


def test_generated_live_policy_authorizes_matching_submission(tmp_path) -> None:
    submission = tmp_path / "broker_submission.json"
    policy_path = tmp_path / "policy.json"
    _write_submission(submission, mode="LIVE", adapter="qmt")
    policy = build_execution_policy(
        mode="LIVE",
        adapter="qmt",
        trade_date="2024-09-09",
        strategy_id="momentum_rank",
        approval_id="approval-1",
        approved_by="operator",
        expires_at="2024-09-09T15:00:00+00:00",
        max_order_count=1,
        max_notional=2000,
    )
    write_execution_policy_json(policy, policy_path)

    report = build_execution_authorization_report(
        broker_submission_path=submission,
        policy_path=policy_path,
        now=datetime(2024, 9, 9, 14, 0, tzinfo=UTC),
    )

    assert report.passed


def _write_submission(path, *, mode: str, adapter: str) -> None:
    path.write_text(
        json.dumps(
            {
                "mode": mode,
                "adapter": adapter,
                "trade_date": "2024-09-09",
                "strategy_id": "momentum_rank",
                "order_count": 1,
                "orders": [
                    {
                        "quantity": 100,
                        "price": 10.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
