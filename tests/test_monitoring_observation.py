from __future__ import annotations

import json
from datetime import date

import pandas as pd

from quant.core.monitoring.observation import (
    build_observation_plan,
    render_observation_plan_markdown,
    write_observation_plan_json,
    write_observation_plan_markdown,
)


def test_observation_plan_recommends_forward_dates(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    bars_path = tmp_path / "daily_bar.csv"
    _write_history(history_path, ["2024-09-09"])
    _write_bars(bars_path, ["2024-09-09", "2024-09-10", "2024-09-11"])

    plan = build_observation_plan(
        history_path=history_path,
        bars_path=bars_path,
        target_days=3,
        max_dates=2,
    )

    assert plan.status == "NEEDS_DATES"
    assert plan.mode == "FORWARD"
    assert plan.observed_days == 1
    assert plan.stable_days == 1
    assert plan.remaining_days == 2
    assert plan.recommended_dates == ["2024-09-10", "2024-09-11"]


def test_observation_plan_recommends_backfill_when_no_forward_dates(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    bars_path = tmp_path / "daily_bar.csv"
    _write_history(history_path, ["2024-09-11"])
    _write_bars(bars_path, ["2024-09-09", "2024-09-10", "2024-09-11"])

    plan = build_observation_plan(
        history_path=history_path,
        bars_path=bars_path,
        target_days=3,
        max_dates=5,
    )

    assert plan.mode == "BACKFILL"
    assert plan.recommended_dates == ["2024-09-09", "2024-09-10"]
    assert "2024-09-10" in render_observation_plan_markdown(plan)


def test_observation_plan_backfills_from_earliest_missing_date_in_target_window(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    bars_path = tmp_path / "daily_bar.csv"
    _write_history(history_path, ["2024-09-10"])
    _write_bars(
        bars_path,
        [
            "2024-09-01",
            "2024-09-02",
            "2024-09-03",
            "2024-09-04",
            "2024-09-05",
            "2024-09-06",
            "2024-09-07",
            "2024-09-08",
            "2024-09-09",
            "2024-09-10",
        ],
    )

    plan = build_observation_plan(
        history_path=history_path,
        bars_path=bars_path,
        target_days=5,
        max_dates=3,
    )

    assert plan.mode == "BACKFILL"
    assert plan.recommended_dates == ["2024-09-06", "2024-09-07", "2024-09-08"]


def test_observation_plan_writers_emit_json_and_markdown(tmp_path) -> None:
    history_path = tmp_path / "daily_history.csv"
    bars_path = tmp_path / "daily_bar.csv"
    _write_history(history_path, ["2024-09-09"])
    _write_bars(bars_path, ["2024-09-09", "2024-09-10"])
    plan = build_observation_plan(
        history_path=history_path,
        bars_path=bars_path,
        target_days=2,
    )

    json_path = write_observation_plan_json(plan, tmp_path / "observation_plan.json")
    markdown_path = write_observation_plan_markdown(plan, tmp_path / "observation_plan.md")

    assert json.loads(json_path.read_text(encoding="utf-8"))["mode"] == "FORWARD"
    assert "Quant Observation Plan" in markdown_path.read_text(encoding="utf-8")


def _write_history(path, trade_dates: list[str]) -> None:
    rows = []
    for index, trade_date in enumerate(trade_dates, start=1):
        rows.append(
            {
                "trade_date": trade_date,
                "recorded_at": f"{trade_date}T10:00:00+00:00",
                "run_id": f"run-{index}",
                "run_status": "SUCCESS",
                "ok": True,
                "data_quality_level": "INFO",
                "reconciliation_diff_count": 0,
                "risk_guard_status": "OK",
                "risk_guard_rejected_orders": 0,
                "pretrade_gate_status": "GO",
                "pretrade_gate_failed_count": 0,
                "failed_health_count": 0,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_bars(path, trade_dates: list[str]) -> None:
    rows = []
    for trade_date in trade_dates:
        rows.append(
            {
                "ts_code": "000001.SZ",
                "trade_date": date.fromisoformat(trade_date),
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.0,
                "volume": 1000,
                "amount": 100000.0,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)
