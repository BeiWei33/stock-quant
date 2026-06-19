from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

import pandas as pd

from quant.core.collector.csv_source import CsvDataSource, CsvDataSourceConfig
from quant.core.models import WorkflowRun
from quant.core.monitoring.history import (
    DailyMonitorCsvStore,
    DailyMonitorJsonlStore,
    DailyMonitorRecordBuilder,
)
from quant.core.monitoring.observation import build_observation_plan, write_observation_plan_json, write_observation_plan_markdown
from quant.core.monitoring.refresh import MonitorRefreshPaths, MonitorRefreshResult, refresh_monitoring
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.workflow.daily import DailyWorkflow, DailyWorkflowConfig


@dataclass(frozen=True)
class ObservationRunConfig:
    plan_path: Path | None = Path("research_store/monitoring/observation_plan.json")
    dates: tuple[str, ...] = ()
    stocks_path: Path = Path("research_store/sample/stocks.csv")
    bars_path: Path = Path("research_store/sample/daily_bar.cleaned.csv")
    benchmark_bars_path: Path | None = None
    benchmark_code: str = "equal_weight"
    paper_store_path: Path = Path("research_store/paper_trading.sqlite3")
    report_root: Path = Path("research_store/monitoring/observation_runs")
    history_csv_path: Path = Path("research_store/monitoring/daily_history.csv")
    history_jsonl_path: Path = Path("research_store/monitoring/daily_history.jsonl")
    account_id: str = "paper"
    strategy_name: str = "momentum_rank"
    factor_name: str = "momentum_60d"
    horizon: int = 5
    quantiles: int = 5
    initial_cash: float = 1_000_000
    apply_fills: bool = True
    quality_check_enabled: bool = True
    fail_on_quality_error: bool = False
    quality_check_weekday_gaps: bool = True
    max_dates: int = 5
    append_jsonl: bool = True
    refresh: bool = True
    refresh_paths: MonitorRefreshPaths = MonitorRefreshPaths()
    target_days: int = 20
    qmt_available: bool = False
    write_dashboard: bool = True
    observation_plan_output_json: Path = Path("research_store/monitoring/observation_plan.json")
    observation_plan_output_md: Path = Path("research_store/monitoring/observation_plan.md")


@dataclass(frozen=True)
class ObservationRunDay:
    trade_date: str
    run_id: str
    status: str
    ok: bool
    summary_path: str
    report_dir: str
    error_msg: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ObservationRunReport:
    status: str
    attempted_days: int
    succeeded_days: int
    failed_days: int
    skipped_days: int
    days: list[ObservationRunDay]
    history_csv_path: str
    history_jsonl_path: str
    refresh_result: dict[str, object] | None
    observation_plan_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "attempted_days": self.attempted_days,
            "succeeded_days": self.succeeded_days,
            "failed_days": self.failed_days,
            "skipped_days": self.skipped_days,
            "days": [day.to_dict() for day in self.days],
            "history_csv_path": self.history_csv_path,
            "history_jsonl_path": self.history_jsonl_path,
            "refresh_result": self.refresh_result,
            "observation_plan_path": self.observation_plan_path,
        }


DailyRunner = Callable[[date, ObservationRunConfig], ObservationRunDay]
RefreshRunner = Callable[[MonitorRefreshPaths, int, bool, bool], MonitorRefreshResult]


def run_observation_dates(
    config: ObservationRunConfig,
    *,
    daily_runner: DailyRunner | None = None,
    refresh_runner: RefreshRunner | None = None,
) -> ObservationRunReport:
    trade_dates = _resolve_trade_dates(config)
    if not trade_dates:
        report = ObservationRunReport(
            status="SKIPPED",
            attempted_days=0,
            succeeded_days=0,
            failed_days=0,
            skipped_days=0,
            days=[],
            history_csv_path=str(config.history_csv_path),
            history_jsonl_path=str(config.history_jsonl_path),
            refresh_result=None,
            observation_plan_path=str(config.observation_plan_output_json),
        )
        _write_run_report(report, config.report_root)
        return report

    runner = daily_runner or _run_one_daily_observation
    days: list[ObservationRunDay] = []
    for trade_date in trade_dates:
        day = runner(trade_date, config)
        days.append(day)
        record = DailyMonitorRecordBuilder(Path(day.summary_path)).build()
        DailyMonitorCsvStore(config.history_csv_path).upsert(record)
        if config.append_jsonl:
            DailyMonitorJsonlStore(config.history_jsonl_path).append(record)

    refresh_result = None
    if config.refresh:
        runner_refresh = refresh_runner or _refresh
        refresh_result = runner_refresh(
            config.refresh_paths,
            config.target_days,
            config.qmt_available,
            config.write_dashboard,
        ).to_dict()

    _refresh_observation_plan(config)
    succeeded = sum(1 for day in days if day.status == "SUCCESS" and day.ok)
    failed = sum(1 for day in days if day.status == "FAILED" or not day.ok)
    report = ObservationRunReport(
        status="SUCCESS" if failed == 0 else "PARTIAL",
        attempted_days=len(days),
        succeeded_days=succeeded,
        failed_days=failed,
        skipped_days=0,
        days=days,
        history_csv_path=str(config.history_csv_path),
        history_jsonl_path=str(config.history_jsonl_path),
        refresh_result=refresh_result,
        observation_plan_path=str(config.observation_plan_output_json),
    )
    _write_run_report(report, config.report_root)
    return report


def write_observation_run_json(report: ObservationRunReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_observation_run_markdown(report: ObservationRunReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_observation_run_markdown(report), encoding="utf-8")
    return path


def render_observation_run_markdown(report: ObservationRunReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Attempted Days", report.attempted_days],
        ["Succeeded Days", report.succeeded_days],
        ["Failed Days", report.failed_days],
        ["Skipped Days", report.skipped_days],
    ]
    day_rows = [
        [day.trade_date, day.status, day.ok, day.run_id, day.summary_path, day.error_msg or "-"]
        for day in report.days
    ]
    return "\n".join(
        [
            "# Quant Observation Run",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            _table(["Trade Date", "Status", "OK", "Run ID", "Summary", "Error"], day_rows)
            if day_rows
            else "-",
            "",
            f"History CSV: `{report.history_csv_path}`",
            f"History JSONL: `{report.history_jsonl_path}`",
            f"Observation Plan: `{report.observation_plan_path}`",
            "",
        ]
    )


def _run_one_daily_observation(trade_date: date, config: ObservationRunConfig) -> ObservationRunDay:
    run_id = uuid4().hex
    started_at = datetime.now(UTC)
    day_dir = config.report_root / trade_date.isoformat()
    report_dir = day_dir / "reports"
    market_store_path = day_dir / "market_data.sqlite3"
    summary_path = day_dir / "daily_summary.json"
    paper_store = SqliteStore(config.paper_store_path)
    paper_store.init_schema()
    paper_store.save_workflow_run(
        WorkflowRun(
            run_id=run_id,
            workflow_name="observation",
            status="RUNNING",
            started_at=started_at,
            trade_date=trade_date,
            summary_path=str(summary_path),
        )
    )
    workflow = DailyWorkflow(
        DailyWorkflowConfig(
            market_store_path=market_store_path,
            paper_store_path=config.paper_store_path,
            report_dir=report_dir,
            account_id=config.account_id,
            strategy_name=config.strategy_name,
            factor_name=config.factor_name,
            horizon=config.horizon,
            quantiles=config.quantiles,
            initial_cash=config.initial_cash,
            apply_fills=config.apply_fills,
            quality_check_enabled=config.quality_check_enabled,
            fail_on_quality_error=config.fail_on_quality_error,
            quality_check_weekday_gaps=config.quality_check_weekday_gaps,
        )
    )
    source = CsvDataSource(
        CsvDataSourceConfig(
            stocks_path=config.stocks_path,
            daily_bars_path=config.bars_path,
            benchmark_bars_path=config.benchmark_bars_path,
            benchmark_code=config.benchmark_code,
        )
    )
    try:
        result = workflow.run(source=source, end_date=trade_date, trade_date=trade_date)
        status = "SUCCESS" if result.ok else "CHECK"
        payload = result.to_dict()
        payload["run_id"] = run_id
        payload["run_status"] = status
        error_msg = ""
        ok = result.ok
    except Exception as exc:
        status = "FAILED"
        error_msg = str(exc)
        ok = False
        payload = {
            "run_id": run_id,
            "run_status": status,
            "trade_date": trade_date.isoformat(),
            "ok": False,
            "error_msg": error_msg,
            "health_checks": [],
        }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paper_store.save_workflow_run(
        WorkflowRun(
            run_id=run_id,
            workflow_name="observation",
            status=status,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            trade_date=trade_date,
            summary_path=str(summary_path),
            error_msg=error_msg,
        )
    )
    return ObservationRunDay(
        trade_date=trade_date.isoformat(),
        run_id=run_id,
        status=status,
        ok=ok,
        summary_path=str(summary_path),
        report_dir=str(report_dir),
        error_msg=error_msg,
    )


def _resolve_trade_dates(config: ObservationRunConfig) -> list[date]:
    values = list(config.dates)
    if not values and config.plan_path is not None and config.plan_path.exists():
        payload = json.loads(config.plan_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            recommended = payload.get("recommended_dates", [])
            if isinstance(recommended, list):
                values = [str(value) for value in recommended]
    dates = [pd.to_datetime(value).date() for value in values if str(value).strip()]
    unique_sorted = sorted(set(dates))
    return unique_sorted[: config.max_dates] if config.max_dates > 0 else unique_sorted


def _refresh(
    paths: MonitorRefreshPaths,
    target_days: int,
    qmt_available: bool,
    write_dashboard: bool,
) -> MonitorRefreshResult:
    return refresh_monitoring(
        paths,
        target_days=target_days,
        qmt_available=qmt_available,
        write_dashboard=write_dashboard,
    )


def _refresh_observation_plan(config: ObservationRunConfig) -> None:
    plan = build_observation_plan(
        history_path=config.history_csv_path,
        bars_path=config.bars_path,
        target_days=config.target_days,
        max_dates=config.max_dates,
    )
    write_observation_plan_json(plan, config.observation_plan_output_json)
    write_observation_plan_markdown(plan, config.observation_plan_output_md)


def _write_run_report(report: ObservationRunReport, report_root: Path) -> None:
    write_observation_run_json(report, report_root / "observation_run.json")
    write_observation_run_markdown(report, report_root / "observation_run.md")


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
