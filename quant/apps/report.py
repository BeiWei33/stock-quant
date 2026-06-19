from __future__ import annotations

import argparse
from pathlib import Path

from quant.core.reporting.daily_report import DailyReportGenerator
from quant.core.execution.audit import append_execution_audit
from quant.core.execution.drift_report import build_drift_report, write_drift_report
from quant.core.reporting.execution_dashboard import (
    ExecutionDashboardPaths,
    build_execution_dashboard,
    write_execution_dashboard_html,
)
from quant.core.reporting.execution_report import (
    ExecutionReportPaths,
    build_execution_day_end_report,
    render_execution_day_end_markdown,
    write_execution_day_end_json,
    write_execution_day_end_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate operational reports.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    daily = subparsers.add_parser("daily", help="Generate a daily Markdown/HTML report.")
    daily.add_argument("--summary", default="research_store/reports/daily_summary.json")
    daily.add_argument("--paper-sqlite", default="research_store/paper_trading.sqlite3")
    daily.add_argument("--account-id", default="paper")
    daily.add_argument("--workflow", default="daily")
    daily.add_argument("--output-md", default="research_store/reports/daily_report.md")
    daily.add_argument("--output-html")
    execution = subparsers.add_parser("execution", help="Generate an execution day-end report.")
    execution.add_argument("--paper-plan", default="research_store/reports/paper_plan.json")
    execution.add_argument("--risk-guard", default="research_store/reports/risk_guard.json")
    execution.add_argument("--broker-submission", default="research_store/reports/broker_submission.json")
    execution.add_argument("--execution-authorization", default="research_store/reports/execution_authorization.json")
    execution.add_argument("--broker-adapter-contract", default="research_store/reports/broker_adapter_contract.json")
    execution.add_argument("--manual-execution", default="research_store/reports/manual_execution.json")
    execution.add_argument("--pretrade-gate", default="research_store/reports/pretrade_gate.json")
    execution.add_argument("--manual-fill-validation", default="research_store/reports/manual_fill_validation.json")
    execution.add_argument("--manual-reconciliation", default="research_store/reports/manual_reconciliation.json")
    execution.add_argument("--monitor-status", default="research_store/monitoring/status_summary.json")
    execution.add_argument("--readiness", default="research_store/monitoring/readiness.json")
    execution.add_argument("--output-json", default="research_store/reports/execution_day_end.json")
    execution.add_argument("--output-md", default="research_store/reports/execution_day_end.md")
    execution.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    execution.add_argument("--no-console", action="store_true")

    drift = subparsers.add_parser("drift", help="Generate an execution drift report (slippage, fill rate, etc.).")
    drift.add_argument("--paper-sqlite", default="research_store/paper_trading.sqlite3")
    drift.add_argument("--account-id", default="paper")
    drift.add_argument("--trade-date")
    drift.add_argument("--output-json", default="research_store/reports/execution_drift.json")
    drift.add_argument("--output-md", default="research_store/reports/execution_drift.md")

    dashboard = subparsers.add_parser("execution-dashboard", help="Generate a single-file execution HTML dashboard.")
    dashboard.add_argument("--execution-day-end", default="research_store/reports/execution_day_end.json")
    dashboard.add_argument("--config-health", default="research_store/monitoring/config_health.json")
    dashboard.add_argument("--readiness", default="research_store/monitoring/readiness.json")
    dashboard.add_argument("--audit-report", default="research_store/reports/execution_audit_report.json")
    dashboard.add_argument("--output-html", default="research_store/reports/execution_dashboard.html")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "daily":
        result = DailyReportGenerator(
            summary_path=Path(args.summary),
            paper_store_path=Path(args.paper_sqlite),
            account_id=args.account_id,
            workflow_name=args.workflow,
        ).generate(
            markdown_path=Path(args.output_md),
            html_path=Path(args.output_html) if args.output_html else None,
        )
        print(f"Wrote daily report for {result.trade_date} to {result.markdown_path}")
        if result.html_path:
            print(f"Wrote HTML report to {result.html_path}")
    if args.command == "execution":
        report = build_execution_day_end_report(
            ExecutionReportPaths(
                paper_plan=Path(args.paper_plan),
                risk_guard=Path(args.risk_guard),
                broker_submission=Path(args.broker_submission),
                execution_authorization=Path(args.execution_authorization),
                broker_adapter_contract=Path(args.broker_adapter_contract),
                manual_execution=Path(args.manual_execution),
                pretrade_gate=Path(args.pretrade_gate),
                manual_fill_validation=Path(args.manual_fill_validation),
                manual_reconciliation=Path(args.manual_reconciliation),
                monitor_status=Path(args.monitor_status),
                readiness=Path(args.readiness),
            )
        )
        json_path = write_execution_day_end_json(report, Path(args.output_json))
        markdown_path = write_execution_day_end_markdown(report, Path(args.output_md))
        append_execution_audit(
            event_type="execution_day_end",
            payload=report.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={"json": json_path, "markdown": markdown_path},
            passed=report.status == "READY",
            summary={
                "blocked_artifacts": [a.name for a in report.artifacts if a.status in {"ERROR", "BLOCK", "REJECTED", "CRITICAL", "FAILED"}],
                "pending_artifacts": [a.name for a in report.artifacts if a.status in {"PENDING", "MISSING"}],
            },
        )
        if not args.no_console:
            print(render_execution_day_end_markdown(report))
        print(f"Wrote execution day-end JSON to {json_path}")
        print(f"Wrote execution day-end Markdown to {markdown_path}")
    if args.command == "execution-dashboard":
        dashboard = build_execution_dashboard(
            ExecutionDashboardPaths(
                execution_day_end=Path(args.execution_day_end),
                config_health=Path(args.config_health),
                readiness=Path(args.readiness),
                audit_report=Path(args.audit_report),
            )
        )
        html_path = write_execution_dashboard_html(dashboard, Path(args.output_html))
        print(f"Wrote execution dashboard HTML to {html_path}")
    if args.command == "drift":
        _generate_drift_report(
            paper_sqlite=Path(args.paper_sqlite),
            account_id=args.account_id,
            trade_date=args.trade_date,
            json_path=Path(args.output_json),
            md_path=Path(args.output_md),
        )


def _generate_drift_report(
    *,
    paper_sqlite: Path,
    account_id: str,
    trade_date: str | None,
    json_path: Path,
    md_path: Path,
) -> None:
    import pandas as pd

    from quant.core.persistence.sqlite_store import SqliteStore

    store = SqliteStore(paper_sqlite)
    store.init_schema()
    if trade_date:
        resolved_date = pd.to_datetime(trade_date).date()
    else:
        run = store.load_latest_workflow_run("daily")
        if run is None or run.trade_date is None:
            raise ValueError("no daily workflow run found; specify --trade-date")
        resolved_date = run.trade_date
    orders = store.load_order_intents(account_id, resolved_date)
    fills = store.load_order_fills(account_id, resolved_date)
    report = build_drift_report(orders=orders, fills=fills, trade_date=resolved_date, account_id=account_id)
    write_drift_report(report, json_path, md_path)
    print(f"Wrote drift report for {resolved_date}")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    if report.fill_count > 0:
        print(f"  Fills: {report.fill_count}, Rate: {report.fill_rate:.1%}, Avg Slippage: {report.avg_slippage_bp:.1f} bp")
    else:
        print("  No fills found for this trade date.")


if __name__ == "__main__":
    main()
