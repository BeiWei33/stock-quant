from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from quant.core.data.repository import CsvDailyBarRepository
from quant.core.monitoring.stability import StabilityReportBuilder
from quant.core.monitoring.status import _normalize
from quant.core.persistence.sqlite_store import SqliteStore


@dataclass(frozen=True)
class ObservationPlan:
    status: str
    mode: str
    target_days: int
    observed_days: int
    stable_days: int
    remaining_days: int
    latest_observed_trade_date: str
    available_trade_dates: int
    recommended_dates: list[str]
    forward_candidates: list[str]
    backfill_candidates: list[str]
    history_path: str
    data_source_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_observation_plan(
    *,
    history_path: Path,
    bars_path: Path | None = None,
    market_sqlite: Path | None = None,
    target_days: int = 20,
    max_dates: int = 5,
) -> ObservationPlan:
    trade_dates = _load_trade_dates(bars_path=bars_path, market_sqlite=market_sqlite)
    observed_dates = _load_observed_dates(history_path)
    stability = StabilityReportBuilder(history_path, target_days=target_days).build()
    latest_observed = max(observed_dates) if observed_dates else None
    remaining_days = max(target_days - stability.stable_days, 0)
    unobserved = [value for value in trade_dates if value not in observed_dates]
    forward = [
        value.isoformat()
        for value in unobserved
        if latest_observed is None or value > latest_observed
    ][:max_dates]
    backfill_source = _backfill_window(
        trade_dates=trade_dates,
        observed_dates=observed_dates,
        latest_observed=latest_observed,
        target_days=target_days,
    )
    backfill = [value.isoformat() for value in backfill_source[:max_dates]]
    mode = "FORWARD" if forward else "BACKFILL" if backfill else "NONE"
    recommended = forward if forward else backfill
    status = "COMPLETE" if remaining_days == 0 else "NEEDS_DATES" if recommended else "NO_CANDIDATES"
    return ObservationPlan(
        status=status,
        mode=mode,
        target_days=target_days,
        observed_days=stability.observed_days,
        stable_days=stability.stable_days,
        remaining_days=remaining_days,
        latest_observed_trade_date=latest_observed.isoformat() if latest_observed else "",
        available_trade_dates=len(trade_dates),
        recommended_dates=recommended[: min(max_dates, remaining_days or max_dates)],
        forward_candidates=forward,
        backfill_candidates=backfill,
        history_path=str(history_path),
        data_source_path=str(market_sqlite or bars_path or ""),
    )


def write_observation_plan_json(plan: ObservationPlan, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_observation_plan_markdown(plan: ObservationPlan, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_observation_plan_markdown(plan), encoding="utf-8")
    return path


def render_observation_plan_markdown(plan: ObservationPlan) -> str:
    summary_rows = [
        ["Status", plan.status],
        ["Mode", plan.mode],
        ["Observed Days", f"{plan.observed_days}/{plan.target_days}"],
        ["Stable Days", plan.stable_days],
        ["Remaining Days", plan.remaining_days],
        ["Latest Observed Trade Date", plan.latest_observed_trade_date or "-"],
        ["Available Trade Dates", plan.available_trade_dates],
    ]
    date_rows = [[index + 1, value] for index, value in enumerate(plan.recommended_dates)]
    return "\n".join(
        [
            "# Quant Observation Plan",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Recommended Dates",
            _table(["#", "Trade Date"], date_rows) if date_rows else "-",
            "",
            f"History: `{plan.history_path}`",
            f"Data Source: `{plan.data_source_path}`",
            "",
        ]
    )


def _load_trade_dates(*, bars_path: Path | None, market_sqlite: Path | None) -> list[pd.Timestamp]:
    if market_sqlite is not None:
        bars = SqliteStore(market_sqlite).load_daily_bars(adj_type="qfq")
        if bars.empty:
            bars = SqliteStore(market_sqlite).load_daily_bars()
    elif bars_path is not None:
        bars = CsvDailyBarRepository(bars_path).load()
    else:
        raise ValueError("either bars_path or market_sqlite is required")
    if bars.empty:
        return []
    return sorted({pd.Timestamp(value).date() for value in bars["trade_date"]})


def _load_observed_dates(history_path: Path) -> set[pd.Timestamp]:
    if not history_path.exists():
        return set()
    df = pd.read_csv(history_path)
    if df.empty:
        return set()
    df = _normalize(df).sort_values(["trade_date", "recorded_at", "run_id"])
    latest_by_day = df.groupby("trade_date", as_index=False, sort=False).tail(1)
    return {pd.Timestamp(value).date() for value in latest_by_day["trade_date"]}


def _backfill_window(
    *,
    trade_dates: list[pd.Timestamp],
    observed_dates: set[pd.Timestamp],
    latest_observed: pd.Timestamp | None,
    target_days: int,
) -> list[pd.Timestamp]:
    if latest_observed is None:
        candidates = trade_dates
    else:
        candidates = [value for value in trade_dates if value <= latest_observed]
    window = candidates[-target_days:] if target_days > 0 else candidates
    return [value for value in window if value not in observed_dates]


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
