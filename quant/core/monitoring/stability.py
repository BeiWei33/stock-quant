from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from quant.core.monitoring.status import _normalize


@dataclass(frozen=True)
class StabilityDay:
    trade_date: str
    run_id: str
    stable: bool
    blockers: str
    run_status: str
    pretrade_gate_status: str
    risk_guard_status: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StabilityReport:
    status: str
    ready_for_live: bool
    target_days: int
    observed_days: int
    stable_days: int
    unstable_days: int
    progress: float
    latest_trade_date: str
    latest_stable: bool
    days: list[StabilityDay]
    history_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "ready_for_live": self.ready_for_live,
            "target_days": self.target_days,
            "observed_days": self.observed_days,
            "stable_days": self.stable_days,
            "unstable_days": self.unstable_days,
            "progress": self.progress,
            "latest_trade_date": self.latest_trade_date,
            "latest_stable": self.latest_stable,
            "days": [day.to_dict() for day in self.days],
            "history_path": self.history_path,
        }


class StabilityReportBuilder:
    def __init__(self, history_path: Path, target_days: int = 20) -> None:
        self.history_path = history_path
        self.target_days = target_days

    def build(self) -> StabilityReport:
        if not self.history_path.exists():
            raise FileNotFoundError(f"monitoring history not found: {self.history_path}")
        df = pd.read_csv(self.history_path)
        if df.empty:
            raise ValueError(f"monitoring history is empty: {self.history_path}")
        df = _normalize(df).sort_values(["trade_date", "recorded_at", "run_id"])
        latest_by_day = df.groupby("trade_date", as_index=False, sort=False).tail(1)
        window = latest_by_day.tail(self.target_days)
        days = [_stability_day(row) for _, row in window.iterrows()]
        stable_days = sum(1 for day in days if day.stable)
        unstable_days = len(days) - stable_days
        ready = len(days) >= self.target_days and unstable_days == 0
        latest = days[-1] if days else None
        return StabilityReport(
            status="READY" if ready else "OBSERVING",
            ready_for_live=ready,
            target_days=self.target_days,
            observed_days=len(days),
            stable_days=stable_days,
            unstable_days=unstable_days,
            progress=min(stable_days / self.target_days, 1.0) if self.target_days > 0 else 0.0,
            latest_trade_date=latest.trade_date if latest else "",
            latest_stable=bool(latest.stable) if latest else False,
            days=days,
            history_path=str(self.history_path),
        )


def write_stability_json(report: StabilityReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_stability_markdown(report: StabilityReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_stability_markdown(report), encoding="utf-8")
    return path


def render_stability_markdown(report: StabilityReport) -> str:
    rows = [
        [day.trade_date, day.stable, day.run_status, day.pretrade_gate_status, day.risk_guard_status, day.blockers or "-"]
        for day in report.days
    ]
    summary_rows = [
        ["Status", report.status],
        ["Ready For Live", report.ready_for_live],
        ["Observed Days", f"{report.observed_days}/{report.target_days}"],
        ["Stable Days", report.stable_days],
        ["Unstable Days", report.unstable_days],
        ["Progress", _percent(report.progress)],
        ["Latest Trade Date", report.latest_trade_date or "-"],
        ["Latest Stable", report.latest_stable],
    ]
    return "\n".join(
        [
            "# Quant Stability Report",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            _table(
                ["Trade Date", "Stable", "Run Status", "Pre-Trade Gate", "Risk Guard", "Blockers"],
                rows,
            ),
            "",
            f"History: `{report.history_path}`",
            "",
        ]
    )


def _stability_day(row: pd.Series) -> StabilityDay:
    blockers = _blockers(row)
    return StabilityDay(
        trade_date=str(row["trade_date"]),
        run_id=str(row["run_id"]),
        stable=not blockers,
        blockers=";".join(blockers),
        run_status=str(row["run_status"]),
        pretrade_gate_status=str(row["pretrade_gate_status"]),
        risk_guard_status=str(row["risk_guard_status"]),
    )


def _blockers(row: pd.Series) -> list[str]:
    blockers: list[str] = []
    if str(row["run_status"]) != "SUCCESS" or not bool(row["ok"]):
        blockers.append("run_status")
    if int(row["failed_health_count"]) > 0:
        blockers.append("health_checks")
    if str(row["data_quality_level"]) in {"ERROR", "WARNING"}:
        blockers.append("data_quality")
    if int(row["reconciliation_diff_count"]) > 0:
        blockers.append("reconciliation")
    if str(row["risk_guard_status"]) == "REJECTED" or int(row["risk_guard_rejected_orders"]) > 0:
        blockers.append("risk_guard")
    if str(row["pretrade_gate_status"]) == "BLOCK" or int(row["pretrade_gate_failed_count"]) > 0:
        blockers.append("pretrade_gate")
    return blockers


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"
