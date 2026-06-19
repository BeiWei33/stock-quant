from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from quant.core.monitoring.observe_run import (
    ObservationRunConfig,
    ObservationRunDay,
    run_observation_dates,
)


def test_observe_run_uses_plan_dates_and_updates_history(tmp_path) -> None:
    plan_path = tmp_path / "observation_plan.json"
    bars_path = tmp_path / "daily_bar.csv"
    _write_plan(plan_path, ["2024-09-03", "2024-09-02", "2024-09-04"])
    _write_bars(bars_path, ["2024-09-02", "2024-09-03", "2024-09-04", "2024-09-05"])

    config = ObservationRunConfig(
        plan_path=plan_path,
        bars_path=bars_path,
        stocks_path=tmp_path / "stocks.csv",
        paper_store_path=tmp_path / "paper.sqlite3",
        report_root=tmp_path / "observation_runs",
        history_csv_path=tmp_path / "daily_history.csv",
        history_jsonl_path=tmp_path / "daily_history.jsonl",
        max_dates=2,
        refresh=False,
        observation_plan_output_json=tmp_path / "observation_plan.out.json",
        observation_plan_output_md=tmp_path / "observation_plan.out.md",
    )

    report = run_observation_dates(config, daily_runner=_fake_daily_runner)

    assert report.status == "SUCCESS"
    assert [day.trade_date for day in report.days] == ["2024-09-02", "2024-09-03"]
    assert (tmp_path / "observation_runs" / "observation_run.json").exists()
    assert (tmp_path / "observation_runs" / "observation_run.md").exists()
    history = pd.read_csv(tmp_path / "daily_history.csv")
    assert history["trade_date"].tolist() == ["2024-09-02", "2024-09-03"]
    assert history["run_status"].tolist() == ["SUCCESS", "SUCCESS"]
    jsonl_lines = (tmp_path / "daily_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(jsonl_lines) == 2


def test_observe_run_explicit_dates_override_plan(tmp_path) -> None:
    plan_path = tmp_path / "observation_plan.json"
    bars_path = tmp_path / "daily_bar.csv"
    _write_plan(plan_path, ["2024-09-02"])
    _write_bars(bars_path, ["2024-09-02", "2024-09-03", "2024-09-04"])
    config = ObservationRunConfig(
        plan_path=plan_path,
        dates=("2024-09-04",),
        bars_path=bars_path,
        stocks_path=tmp_path / "stocks.csv",
        paper_store_path=tmp_path / "paper.sqlite3",
        report_root=tmp_path / "observation_runs",
        history_csv_path=tmp_path / "daily_history.csv",
        history_jsonl_path=tmp_path / "daily_history.jsonl",
        refresh=False,
        append_jsonl=False,
        observation_plan_output_json=tmp_path / "observation_plan.out.json",
        observation_plan_output_md=tmp_path / "observation_plan.out.md",
    )

    report = run_observation_dates(config, daily_runner=_fake_daily_runner)

    assert [day.trade_date for day in report.days] == ["2024-09-04"]
    assert not (tmp_path / "daily_history.jsonl").exists()
    assert json.loads((tmp_path / "observation_plan.out.json").read_text(encoding="utf-8"))[
        "observed_days"
    ] == 1


def test_observe_run_skips_when_no_dates(tmp_path) -> None:
    config = ObservationRunConfig(
        plan_path=None,
        dates=(),
        report_root=tmp_path / "observation_runs",
        history_csv_path=tmp_path / "daily_history.csv",
        history_jsonl_path=tmp_path / "daily_history.jsonl",
        refresh=False,
    )

    report = run_observation_dates(config, daily_runner=_fake_daily_runner)

    assert report.status == "SKIPPED"
    assert report.attempted_days == 0
    assert (tmp_path / "observation_runs" / "observation_run.json").exists()


def _fake_daily_runner(trade_date: date, config: ObservationRunConfig) -> ObservationRunDay:
    run_id = f"fake-{trade_date.isoformat()}"
    day_dir = config.report_root / trade_date.isoformat()
    summary_path = day_dir / "daily_summary.json"
    payload = {
        "trade_date": trade_date.isoformat(),
        "run_id": run_id,
        "run_status": "SUCCESS",
        "ok": True,
        "collected_stocks": 3,
        "collected_daily_bars": 30,
        "collected_benchmark_bars": 0,
        "data_quality_level": "INFO",
        "order_count": 1,
        "rejected_order_count": 0,
        "fill_count": 1,
        "fill_rejected_count": 0,
        "snapshot": {
            "total_asset": 1_000_000.0,
            "cash": 900_000.0,
            "market_value": 100_000.0,
            "total_position_ratio": 0.1,
            "daily_return": 0.001,
            "cum_return": 0.001,
            "drawdown": 0.0,
            "excess_return": 0.0,
        },
        "health_checks": [{"name": "fake", "ok": True, "detail": ""}],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ObservationRunDay(
        trade_date=trade_date.isoformat(),
        run_id=run_id,
        status="SUCCESS",
        ok=True,
        summary_path=str(summary_path),
        report_dir=str(day_dir),
    )


def _write_plan(path: Path, dates: list[str]) -> None:
    path.write_text(
        json.dumps({"recommended_dates": dates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_bars(path: Path, trade_dates: list[str]) -> None:
    rows = [
        {
            "ts_code": "000001.SZ",
            "trade_date": value,
            "open": 10.0,
            "high": 10.1,
            "low": 9.9,
            "close": 10.0,
            "volume": 1000,
            "amount": 100000.0,
        }
        for value in trade_dates
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
