from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from quant.core.collector.base import MarketDataSource
from quant.core.data.quality import DataQualityAnalyzer, write_quality_json, write_quality_markdown
from quant.core.models import OrderRiskResult, PortfolioSnapshot, RiskDecision
from quant.core.monitoring.health import HealthCheck, require_non_empty
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.research.alpha_validation import validate_factor
from quant.core.research.factor_factory import build_factor
from quant.core.research.report import AlphaResearchReportWriter, ResearchReportPaths
from quant.core.strategy.admission import StrategyAdmissionPolicy
from quant.core.strategy.factory import build_strategy
from quant.core.trader.paper import PaperTradingEngine
from quant.core.trader.simulator import PaperAccountState, PaperExecutionSimulator


@dataclass(frozen=True)
class DailyWorkflowConfig:
    market_store_path: Path
    paper_store_path: Path
    report_dir: Path
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


@dataclass(frozen=True)
class DailyWorkflowResult:
    trade_date: date
    collected_stocks: int
    collected_daily_bars: int
    collected_benchmark_bars: int
    data_quality_json_path: str
    data_quality_markdown_path: str
    data_quality_level: str
    research_json_path: str
    research_markdown_path: str
    order_count: int
    rejected_order_count: int
    fill_count: int
    fill_rejected_count: int
    snapshot: PortfolioSnapshot | None
    health_checks: list[HealthCheck]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.health_checks)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["trade_date"] = self.trade_date.isoformat()
        data["snapshot"] = self.snapshot.to_dict() if self.snapshot is not None else None
        data["health_checks"] = [asdict(check) for check in self.health_checks]
        data["ok"] = self.ok
        return data


class DailyWorkflow:
    def __init__(self, config: DailyWorkflowConfig) -> None:
        self.config = config
        self.market_store = SqliteStore(config.market_store_path)
        self.paper_store = SqliteStore(config.paper_store_path)

    def run(
        self,
        *,
        source: MarketDataSource,
        start_date: date | None = None,
        end_date: date | None = None,
        trade_date: date | None = None,
    ) -> DailyWorkflowResult:
        self.market_store.init_schema()
        self.paper_store.init_schema()

        collection = source.collect(start_date=start_date, end_date=end_date)
        self.market_store.save_stocks(collection.stocks)
        self.market_store.save_daily_bars(collection.daily_bars)
        self.market_store.save_benchmark_bars(collection.benchmark_bars)

        bars = self.market_store.load_daily_bars(adj_type="qfq")
        if bars.empty:
            bars = self.market_store.load_daily_bars()
        stocks = self.market_store.load_stocks()
        if bars.empty:
            raise ValueError("daily workflow cannot continue without daily bars")
        if stocks.empty:
            raise ValueError("daily workflow cannot continue without stocks")

        resolved_trade_date = trade_date or max(bars["trade_date"])
        quality_report = None
        quality_json_path = ""
        quality_markdown_path = ""
        quality_level = "SKIPPED"
        if self.config.quality_check_enabled:
            quality_report = DataQualityAnalyzer(
                check_weekday_gaps=self.config.quality_check_weekday_gaps
            ).analyze(bars=bars, stocks=stocks)
            quality_json_path = str(write_quality_json(quality_report, self.config.report_dir / "data_quality.json"))
            quality_markdown_path = str(
                write_quality_markdown(quality_report, self.config.report_dir / "data_quality.md")
            )
            quality_level = quality_report.level
            if self.config.fail_on_quality_error and not quality_report.ok:
                raise ValueError(
                    f"data quality gate failed: level={quality_report.level}, "
                    f"report={quality_markdown_path}"
                )

        all_dates = sorted(bars["trade_date"].unique())
        resolved_execution_date = None
        execution_bars = None
        if all_dates:
            idx = all_dates.index(resolved_trade_date) if resolved_trade_date in all_dates else -1
            if idx >= 0 and idx + 1 < len(all_dates):
                resolved_execution_date = all_dates[idx + 1]
                execution_bars = bars[bars["trade_date"] == resolved_execution_date]
        if resolved_execution_date is None:
            resolved_execution_date = resolved_trade_date

        report_paths = self._run_research(bars)
        plan, fill_state = self._run_paper_trading(
            bars=bars,
            stocks=stocks,
            trade_date=resolved_trade_date,
            execution_date=resolved_execution_date,
            execution_bars=execution_bars,
            research_report_path=report_paths.markdown_path,
        )
        health_checks = self._health_checks(
            collected_stocks=len(collection.stocks),
            collected_daily_bars=len(collection.daily_bars),
            data_quality_ok=quality_report.ok if quality_report is not None else True,
            data_quality_level=quality_level,
            data_quality_report=Path(quality_markdown_path) if quality_markdown_path else None,
            research_report=report_paths.markdown_path,
            order_count=len(plan.order_intents),
            snapshot=fill_state.snapshot if fill_state else None,
        )

        return DailyWorkflowResult(
            trade_date=resolved_trade_date,
            collected_stocks=len(collection.stocks),
            collected_daily_bars=len(collection.daily_bars),
            collected_benchmark_bars=len(collection.benchmark_bars),
            data_quality_json_path=quality_json_path,
            data_quality_markdown_path=quality_markdown_path,
            data_quality_level=quality_level,
            research_json_path=str(report_paths.json_path),
            research_markdown_path=str(report_paths.markdown_path),
            order_count=len(plan.order_intents),
            rejected_order_count=len(plan.rejected_order_intents),
            fill_count=len(fill_state.fills) if fill_state else 0,
            fill_rejected_count=len(fill_state.rejected_orders) if fill_state else 0,
            snapshot=fill_state.snapshot if fill_state else None,
            health_checks=health_checks,
        )

    def _run_research(self, bars: pd.DataFrame) -> ResearchReportPaths:
        factor = build_factor(self.config.factor_name)
        factor_values = factor.calculate(bars)
        result = validate_factor(
            bars=bars,
            factor_values=factor_values,
            factor_name=factor.name,
            horizon=self.config.horizon,
            quantiles=self.config.quantiles,
        )
        return AlphaResearchReportWriter().write(result, self.config.report_dir / "alpha")

    def _run_paper_trading(
        self,
        *,
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        trade_date: date,
        execution_date: date,
        execution_bars: pd.DataFrame | None = None,
        research_report_path: Path,
    ):
        previous_snapshot = self.paper_store.load_latest_portfolio_snapshot(
            self.config.account_id, before_date=trade_date
        )
        current_positions = None
        if self.config.apply_fills:
            current_positions = self.paper_store.load_latest_positions(
                self.config.account_id, before_date=trade_date
            )
            if current_positions.empty:
                current_positions = None
        total_asset = previous_snapshot.total_asset if previous_snapshot else self.config.initial_cash
        engine = PaperTradingEngine(admission_policy=StrategyAdmissionPolicy())
        plan = engine.build_plan(
            trade_date=trade_date,
            bars=bars,
            stocks=stocks,
            strategy=build_strategy(self.config.strategy_name),
            account_id=self.config.account_id,
            total_asset=total_asset,
            current_positions=current_positions,
            research_report_path=str(research_report_path),
            strategy_status="paper",
        )

        fill_state: PaperAccountState | None = None
        if self.config.apply_fills:
            exec_bars = execution_bars if execution_bars is not None else bars[bars["trade_date"] == trade_date]
            fill_state = PaperExecutionSimulator().apply_orders(
                account_id=self.config.account_id,
                trade_date=execution_date,
                orders=plan.order_intents,
                latest_bars=exec_bars,
                previous_positions=current_positions,
                previous_snapshot=previous_snapshot,
                initial_cash=self.config.initial_cash,
            )

        self.paper_store.save_strategy(plan.strategy_registration)
        self.paper_store.save_universe_snapshot("a_share_v1", plan.trade_date, plan.universe_snapshot)
        self.paper_store.save_signals(plan.signals)
        self.paper_store.save_order_intents(plan.order_intents)
        self.paper_store.save_order_risk_results(
            [
                *[
                    OrderRiskResult(order=intent, decision=RiskDecision.allow())
                    for intent in plan.order_intents
                ],
                *plan.rejected_order_intents,
            ]
        )
        if fill_state is not None:
            self.paper_store.save_order_fills(fill_state.fills)
            self.paper_store.save_positions(fill_state.positions)
            self.paper_store.save_portfolio_snapshots([fill_state.snapshot])
        return plan, fill_state

    def _health_checks(
        self,
        *,
        collected_stocks: int,
        collected_daily_bars: int,
        data_quality_ok: bool,
        data_quality_level: str,
        data_quality_report: Path | None,
        research_report: Path,
        order_count: int,
        snapshot: PortfolioSnapshot | None,
    ) -> list[HealthCheck]:
        checks = [
            require_non_empty("collected_stocks", collected_stocks),
            require_non_empty("collected_daily_bars", collected_daily_bars),
            HealthCheck(
                "data_quality_ok",
                data_quality_ok,
                f"level={data_quality_level}; report={data_quality_report or ''}",
            ),
            HealthCheck("research_report_exists", research_report.exists(), str(research_report)),
            HealthCheck("orders_evaluated", order_count >= 0, f"count={order_count}"),
        ]
        if self.config.apply_fills:
            checks.append(HealthCheck("portfolio_snapshot_created", snapshot is not None))
        return checks
