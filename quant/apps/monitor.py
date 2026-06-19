from __future__ import annotations

import argparse
from pathlib import Path

from quant.core.monitoring.alerts import (
    evaluate_monitor_alerts,
    render_alerts_markdown,
    write_alerts_json,
    write_alerts_markdown,
)
from quant.core.monitoring.config_health import (
    ConfigHealthPaths,
    build_config_health_report,
    render_config_health_markdown,
    write_config_health_json,
    write_config_health_markdown,
)
from quant.core.monitoring.history import (
    DailyMonitorCsvStore,
    DailyMonitorJsonlStore,
    DailyMonitorRecordBuilder,
)
from quant.core.monitoring.metrics import (
    build_monitor_metrics,
    write_grafana_dashboard,
    write_metrics_json,
    write_prometheus_metrics,
)
from quant.core.monitoring.observation import (
    build_observation_plan,
    render_observation_plan_markdown,
    write_observation_plan_json,
    write_observation_plan_markdown,
)
from quant.core.monitoring.observe_run import ObservationRunConfig, run_observation_dates
from quant.core.monitoring.readiness import (
    build_readiness_report,
    render_readiness_markdown,
    write_readiness_json,
    write_readiness_markdown,
)
from quant.core.monitoring.refresh import MonitorRefreshPaths, refresh_monitoring
from quant.core.monitoring.status import (
    MonitorStatusBuilder,
    render_status_markdown,
    write_status_json,
    write_status_markdown,
)
from quant.core.monitoring.stability import (
    StabilityReportBuilder,
    render_stability_markdown,
    write_stability_json,
    write_stability_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local monitoring history artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    history = subparsers.add_parser("history", help="Upsert daily monitoring history.")
    history.add_argument("--summary", default="research_store/reports/daily_summary.json")
    history.add_argument("--cleaning-report", default=None)
    history.add_argument("--reconciliation-report", default=None)
    history.add_argument("--risk-guard-audit", default=None)
    history.add_argument("--pretrade-gate", default=None)
    history.add_argument("--csv", default="research_store/monitoring/daily_history.csv")
    history.add_argument("--jsonl", default="research_store/monitoring/daily_history.jsonl")
    history.add_argument("--no-jsonl", action="store_true")
    status = subparsers.add_parser("status", help="Summarize recent monitoring health.")
    status.add_argument("--history", default="research_store/monitoring/daily_history.csv")
    status.add_argument("--limit", type=int, default=20)
    status.add_argument("--output-json", default="research_store/monitoring/status_summary.json")
    status.add_argument("--output-md", default="research_store/monitoring/status_summary.md")
    status.add_argument("--all-runs", action="store_true")
    status.add_argument("--no-console", action="store_true")
    metrics = subparsers.add_parser("metrics", help="Export monitoring metrics for Prometheus/Grafana.")
    metrics.add_argument("--status-json", default="research_store/monitoring/status_summary.json")
    metrics.add_argument("--history", default="research_store/monitoring/daily_history.csv")
    metrics.add_argument("--output-prom", default="research_store/monitoring/metrics.prom")
    metrics.add_argument("--output-json", default="research_store/monitoring/metrics.json")
    metrics.add_argument("--grafana-dashboard", default="research_store/monitoring/grafana_dashboard.json")
    metrics.add_argument("--no-dashboard", action="store_true")
    alerts = subparsers.add_parser("alerts", help="Evaluate local monitoring alert rules.")
    alerts.add_argument("--status-json", default="research_store/monitoring/status_summary.json")
    alerts.add_argument("--output-json", default="research_store/monitoring/alerts.json")
    alerts.add_argument("--output-md", default="research_store/monitoring/alerts.md")
    alerts.add_argument("--no-console", action="store_true")
    stability = subparsers.add_parser("stability", help="Build 20-day paper trading stability report.")
    stability.add_argument("--history", default="research_store/monitoring/daily_history.csv")
    stability.add_argument("--target-days", type=int, default=20)
    stability.add_argument("--output-json", default="research_store/monitoring/stability.json")
    stability.add_argument("--output-md", default="research_store/monitoring/stability.md")
    stability.add_argument("--no-console", action="store_true")
    readiness = subparsers.add_parser("readiness", help="Build paper/live readiness report.")
    readiness.add_argument("--alerts", default="research_store/monitoring/alerts.json")
    readiness.add_argument("--pretrade-gate", default="research_store/reports/pretrade_gate.json")
    readiness.add_argument("--stability", default="research_store/monitoring/stability.json")
    readiness.add_argument("--qmt-available", action="store_true")
    readiness.add_argument("--output-json", default="research_store/monitoring/readiness.json")
    readiness.add_argument("--output-md", default="research_store/monitoring/readiness.md")
    readiness.add_argument("--no-console", action="store_true")
    refresh = subparsers.add_parser("refresh", help="Refresh all derived monitoring artifacts.")
    refresh.add_argument("--history", default="research_store/monitoring/daily_history.csv")
    refresh.add_argument("--pretrade-gate", default="research_store/reports/pretrade_gate.json")
    refresh.add_argument("--limit", type=int, default=20)
    refresh.add_argument("--target-days", type=int, default=20)
    refresh.add_argument("--qmt-available", action="store_true")
    refresh.add_argument("--status-json", default="research_store/monitoring/status_summary.json")
    refresh.add_argument("--status-md", default="research_store/monitoring/status_summary.md")
    refresh.add_argument("--alerts-json", default="research_store/monitoring/alerts.json")
    refresh.add_argument("--alerts-md", default="research_store/monitoring/alerts.md")
    refresh.add_argument("--metrics-prom", default="research_store/monitoring/metrics.prom")
    refresh.add_argument("--metrics-json", default="research_store/monitoring/metrics.json")
    refresh.add_argument("--grafana-dashboard", default="research_store/monitoring/grafana_dashboard.json")
    refresh.add_argument("--stability-json", default="research_store/monitoring/stability.json")
    refresh.add_argument("--stability-md", default="research_store/monitoring/stability.md")
    refresh.add_argument("--readiness-json", default="research_store/monitoring/readiness.json")
    refresh.add_argument("--readiness-md", default="research_store/monitoring/readiness.md")
    refresh.add_argument("--no-dashboard", action="store_true")
    observation = subparsers.add_parser(
        "observation-plan",
        help="Plan the next trade dates for the 20-day paper observation window.",
    )
    observation.add_argument("--history", default="research_store/monitoring/daily_history.csv")
    observation.add_argument("--bars", default="research_store/sample/daily_bar.cleaned.csv")
    observation.add_argument("--market-sqlite", default=None)
    observation.add_argument("--target-days", type=int, default=20)
    observation.add_argument("--max-dates", type=int, default=5)
    observation.add_argument("--output-json", default="research_store/monitoring/observation_plan.json")
    observation.add_argument("--output-md", default="research_store/monitoring/observation_plan.md")
    observation.add_argument("--no-console", action="store_true")
    observe_run = subparsers.add_parser(
        "observe-run",
        help="Run the recommended paper observation dates and update monitoring history.",
    )
    observe_run.add_argument("--plan", default="research_store/monitoring/observation_plan.json")
    observe_run.add_argument("--date", dest="dates", action="append", default=[])
    observe_run.add_argument("--stocks", default="research_store/sample/stocks.csv")
    observe_run.add_argument("--bars", default="research_store/sample/daily_bar.cleaned.csv")
    observe_run.add_argument("--benchmark-bars", default=None)
    observe_run.add_argument("--benchmark-code", default="equal_weight")
    observe_run.add_argument("--paper-sqlite", default="research_store/paper_trading.sqlite3")
    observe_run.add_argument("--report-root", default="research_store/monitoring/observation_runs")
    observe_run.add_argument("--history", default="research_store/monitoring/daily_history.csv")
    observe_run.add_argument("--jsonl", default="research_store/monitoring/daily_history.jsonl")
    observe_run.add_argument("--no-jsonl", action="store_true")
    observe_run.add_argument("--account-id", default="paper")
    observe_run.add_argument("--strategy", default="momentum_rank")
    observe_run.add_argument("--factor", default="momentum_60d")
    observe_run.add_argument("--horizon", type=int, default=5)
    observe_run.add_argument("--quantiles", type=int, default=5)
    observe_run.add_argument("--initial-cash", type=float, default=1_000_000)
    observe_run.add_argument("--max-dates", type=int, default=5)
    observe_run.add_argument("--target-days", type=int, default=20)
    observe_run.add_argument("--no-apply-fills", action="store_true")
    observe_run.add_argument("--no-quality-check", action="store_true")
    observe_run.add_argument("--fail-on-quality-error", action="store_true")
    observe_run.add_argument("--no-quality-weekday-gaps", action="store_true")
    observe_run.add_argument("--no-refresh", action="store_true")
    observe_run.add_argument("--qmt-available", action="store_true")
    observe_run.add_argument("--no-dashboard", action="store_true")
    observe_run.add_argument("--status-json", default="research_store/monitoring/status_summary.json")
    observe_run.add_argument("--status-md", default="research_store/monitoring/status_summary.md")
    observe_run.add_argument("--alerts-json", default="research_store/monitoring/alerts.json")
    observe_run.add_argument("--alerts-md", default="research_store/monitoring/alerts.md")
    observe_run.add_argument("--metrics-prom", default="research_store/monitoring/metrics.prom")
    observe_run.add_argument("--metrics-json", default="research_store/monitoring/metrics.json")
    observe_run.add_argument("--grafana-dashboard", default="research_store/monitoring/grafana_dashboard.json")
    observe_run.add_argument("--stability-json", default="research_store/monitoring/stability.json")
    observe_run.add_argument("--stability-md", default="research_store/monitoring/stability.md")
    observe_run.add_argument("--readiness-json", default="research_store/monitoring/readiness.json")
    observe_run.add_argument("--readiness-md", default="research_store/monitoring/readiness.md")
    observe_run.add_argument("--pretrade-gate", default="research_store/reports/pretrade_gate.json")
    observe_run.add_argument("--observation-plan-json", default="research_store/monitoring/observation_plan.json")
    observe_run.add_argument("--observation-plan-md", default="research_store/monitoring/observation_plan.md")
    observe_run.add_argument("--no-console", action="store_true")
    config_check = subparsers.add_parser(
        "config-check",
        help="Validate local config files and execution/monitoring artifacts.",
    )
    config_check.add_argument("--stocks", default="research_store/sample/stocks.csv")
    config_check.add_argument("--bars", default="research_store/sample/daily_bar.cleaned.csv")
    config_check.add_argument("--daily-config", default="config/daily.yaml")
    config_check.add_argument("--cleaning-config", default="config/cleaning.yaml")
    config_check.add_argument("--risk-guard-control", default="research_store/state/risk_guard_control.env")
    config_check.add_argument("--execution-policy", default="config/execution_policy.generated.json")
    config_check.add_argument("--broker-submission", default="research_store/reports/broker_submission.json")
    config_check.add_argument("--execution-authorization", default="research_store/reports/execution_authorization.json")
    config_check.add_argument("--broker-adapter-contract", default="research_store/reports/broker_adapter_contract.json")
    config_check.add_argument("--pretrade-gate", default="research_store/reports/pretrade_gate.json")
    config_check.add_argument("--manual-order-ticket", default="research_store/reports/manual_order_ticket.csv")
    config_check.add_argument("--manual-fill-template", default="research_store/reports/manual_fill_template.csv")
    config_check.add_argument("--manual-fill-validation", default="research_store/reports/manual_fill_validation.json")
    config_check.add_argument("--execution-day-end", default="research_store/reports/execution_day_end.json")
    config_check.add_argument("--monitor-status", default="research_store/monitoring/status_summary.json")
    config_check.add_argument("--readiness", default="research_store/monitoring/readiness.json")
    config_check.add_argument("--history", default="research_store/monitoring/daily_history.csv")
    config_check.add_argument("--output-json", default="research_store/monitoring/config_health.json")
    config_check.add_argument("--output-md", default="research_store/monitoring/config_health.md")
    config_check.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "history":
        record = DailyMonitorRecordBuilder(
            Path(args.summary),
            cleaning_report_path=Path(args.cleaning_report) if args.cleaning_report else None,
            reconciliation_report_path=Path(args.reconciliation_report) if args.reconciliation_report else None,
            risk_guard_audit_path=Path(args.risk_guard_audit) if args.risk_guard_audit else None,
            pretrade_gate_report_path=Path(args.pretrade_gate) if args.pretrade_gate else None,
        ).build()
        csv_path = DailyMonitorCsvStore(Path(args.csv)).upsert(record)
        print(f"Upserted monitoring history to {csv_path}")
        if not args.no_jsonl:
            jsonl_path = DailyMonitorJsonlStore(Path(args.jsonl)).append(record)
            print(f"Appended monitoring audit record to {jsonl_path}")
    if args.command == "status":
        summary = MonitorStatusBuilder(
            Path(args.history),
            limit=args.limit,
            latest_per_trade_date=not args.all_runs,
        ).build()
        json_path = write_status_json(summary, Path(args.output_json))
        markdown_path = write_status_markdown(summary, Path(args.output_md))
        if not args.no_console:
            print(render_status_markdown(summary))
        print(f"Wrote monitor status JSON to {json_path}")
        print(f"Wrote monitor status Markdown to {markdown_path}")
    if args.command == "metrics":
        samples = build_monitor_metrics(
            Path(args.status_json),
            history_path=Path(args.history) if args.history else None,
        )
        prom_path = write_prometheus_metrics(samples, Path(args.output_prom))
        json_path = write_metrics_json(samples, Path(args.output_json))
        print(f"Wrote Prometheus metrics to {prom_path}")
        print(f"Wrote metrics JSON to {json_path}")
        if not args.no_dashboard:
            dashboard_path = write_grafana_dashboard(Path(args.grafana_dashboard))
            print(f"Wrote Grafana dashboard template to {dashboard_path}")
    if args.command == "alerts":
        evaluation = evaluate_monitor_alerts(Path(args.status_json))
        json_path = write_alerts_json(evaluation, Path(args.output_json))
        markdown_path = write_alerts_markdown(evaluation, Path(args.output_md))
        if not args.no_console:
            print(render_alerts_markdown(evaluation))
        print(f"Wrote monitor alerts JSON to {json_path}")
        print(f"Wrote monitor alerts Markdown to {markdown_path}")
    if args.command == "stability":
        report = StabilityReportBuilder(
            Path(args.history),
            target_days=args.target_days,
        ).build()
        json_path = write_stability_json(report, Path(args.output_json))
        markdown_path = write_stability_markdown(report, Path(args.output_md))
        if not args.no_console:
            print(render_stability_markdown(report))
        print(f"Wrote stability JSON to {json_path}")
        print(f"Wrote stability Markdown to {markdown_path}")
    if args.command == "readiness":
        report = build_readiness_report(
            alerts_path=Path(args.alerts),
            pretrade_gate_path=Path(args.pretrade_gate),
            stability_path=Path(args.stability),
            qmt_available=bool(args.qmt_available),
        )
        json_path = write_readiness_json(report, Path(args.output_json))
        markdown_path = write_readiness_markdown(report, Path(args.output_md))
        if not args.no_console:
            print(render_readiness_markdown(report))
        print(f"Wrote readiness JSON to {json_path}")
        print(f"Wrote readiness Markdown to {markdown_path}")
    if args.command == "refresh":
        result = refresh_monitoring(
            MonitorRefreshPaths(
                history=Path(args.history),
                pretrade_gate=Path(args.pretrade_gate),
                status_json=Path(args.status_json),
                status_md=Path(args.status_md),
                alerts_json=Path(args.alerts_json),
                alerts_md=Path(args.alerts_md),
                metrics_prom=Path(args.metrics_prom),
                metrics_json=Path(args.metrics_json),
                grafana_dashboard=Path(args.grafana_dashboard),
                stability_json=Path(args.stability_json),
                stability_md=Path(args.stability_md),
                readiness_json=Path(args.readiness_json),
                readiness_md=Path(args.readiness_md),
            ),
            limit=args.limit,
            target_days=args.target_days,
            qmt_available=bool(args.qmt_available),
            write_dashboard=not args.no_dashboard,
        )
        print(
            "Refreshed monitoring artifacts: "
            f"level={result.level}, alerts={result.alerts_status}, "
            f"stability={result.stability_status}, readiness={result.readiness_status}"
        )
    if args.command == "observation-plan":
        plan = build_observation_plan(
            history_path=Path(args.history),
            bars_path=Path(args.bars) if args.bars and not args.market_sqlite else None,
            market_sqlite=Path(args.market_sqlite) if args.market_sqlite else None,
            target_days=args.target_days,
            max_dates=args.max_dates,
        )
        json_path = write_observation_plan_json(plan, Path(args.output_json))
        markdown_path = write_observation_plan_markdown(plan, Path(args.output_md))
        if not args.no_console:
            print(render_observation_plan_markdown(plan))
        print(f"Wrote observation plan JSON to {json_path}")
        print(f"Wrote observation plan Markdown to {markdown_path}")
    if args.command == "observe-run":
        report = run_observation_dates(
            ObservationRunConfig(
                plan_path=Path(args.plan) if args.plan and not args.dates else None,
                dates=tuple(args.dates),
                stocks_path=Path(args.stocks),
                bars_path=Path(args.bars),
                benchmark_bars_path=Path(args.benchmark_bars) if args.benchmark_bars else None,
                benchmark_code=args.benchmark_code,
                paper_store_path=Path(args.paper_sqlite),
                report_root=Path(args.report_root),
                history_csv_path=Path(args.history),
                history_jsonl_path=Path(args.jsonl),
                account_id=args.account_id,
                strategy_name=args.strategy,
                factor_name=args.factor,
                horizon=args.horizon,
                quantiles=args.quantiles,
                initial_cash=args.initial_cash,
                apply_fills=not args.no_apply_fills,
                quality_check_enabled=not args.no_quality_check,
                fail_on_quality_error=bool(args.fail_on_quality_error),
                quality_check_weekday_gaps=not args.no_quality_weekday_gaps,
                max_dates=args.max_dates,
                append_jsonl=not args.no_jsonl,
                refresh=not args.no_refresh,
                refresh_paths=MonitorRefreshPaths(
                    history=Path(args.history),
                    pretrade_gate=Path(args.pretrade_gate),
                    status_json=Path(args.status_json),
                    status_md=Path(args.status_md),
                    alerts_json=Path(args.alerts_json),
                    alerts_md=Path(args.alerts_md),
                    metrics_prom=Path(args.metrics_prom),
                    metrics_json=Path(args.metrics_json),
                    grafana_dashboard=Path(args.grafana_dashboard),
                    stability_json=Path(args.stability_json),
                    stability_md=Path(args.stability_md),
                    readiness_json=Path(args.readiness_json),
                    readiness_md=Path(args.readiness_md),
                ),
                target_days=args.target_days,
                qmt_available=bool(args.qmt_available),
                write_dashboard=not args.no_dashboard,
                observation_plan_output_json=Path(args.observation_plan_json),
                observation_plan_output_md=Path(args.observation_plan_md),
            )
        )
        if not args.no_console:
            print(f"Observation run status: {report.status}")
            for day in report.days:
                print(f"{day.trade_date}: {day.status} ok={day.ok} summary={day.summary_path}")
        print(f"Wrote observation run report to {Path(args.report_root) / 'observation_run.json'}")
    if args.command == "config-check":
        report = build_config_health_report(
            ConfigHealthPaths(
                stocks=Path(args.stocks),
                bars=Path(args.bars),
                daily_config=Path(args.daily_config),
                cleaning_config=Path(args.cleaning_config),
                risk_guard_control=Path(args.risk_guard_control),
                execution_policy=Path(args.execution_policy),
                broker_submission=Path(args.broker_submission),
                execution_authorization=Path(args.execution_authorization),
                broker_adapter_contract=Path(args.broker_adapter_contract),
                pretrade_gate=Path(args.pretrade_gate),
                manual_order_ticket=Path(args.manual_order_ticket),
                manual_fill_template=Path(args.manual_fill_template),
                manual_fill_validation=Path(args.manual_fill_validation),
                execution_day_end=Path(args.execution_day_end),
                monitor_status=Path(args.monitor_status),
                readiness=Path(args.readiness),
                history=Path(args.history),
            )
        )
        json_path = write_config_health_json(report, Path(args.output_json))
        markdown_path = write_config_health_markdown(report, Path(args.output_md))
        if not args.no_console:
            print(render_config_health_markdown(report))
        print(f"Wrote config health JSON to {json_path}")
        print(f"Wrote config health Markdown to {markdown_path}")


if __name__ == "__main__":
    main()
