from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant.core.execution.adapters import (
    DryRunBrokerAdapter,
    QmtBrokerAdapterSkeleton,
    build_broker_adapter_contract_report,
    render_broker_adapter_contract_markdown,
    write_broker_adapter_contract_json,
    write_broker_adapter_contract_markdown,
)
from quant.core.execution.broker import (
    build_dry_run_submission,
    render_submission_markdown,
    write_submission_json,
    write_submission_markdown,
)
from quant.core.execution.authorization import (
    build_execution_policy,
    build_execution_authorization_report,
    render_execution_authorization_markdown,
    render_execution_policy_markdown,
    write_execution_authorization_json,
    write_execution_authorization_markdown,
    write_execution_policy_json,
    write_execution_policy_markdown,
)
from quant.core.execution.audit import append_execution_audit
from quant.core.execution.audit import (
    build_execution_audit_report,
    read_execution_audit_events,
    render_execution_audit_report_markdown,
    write_execution_audit_report_json,
    write_execution_audit_report_markdown,
)
from quant.core.execution.fill_import import (
    import_manual_fills,
    load_fill_column_mapping,
    render_manual_fill_import_markdown,
    write_manual_fill_import_json,
    write_manual_fill_import_markdown,
)
from quant.core.execution.manual import (
    build_manual_execution_package,
    render_manual_execution_markdown,
    write_manual_execution_json,
    write_manual_execution_markdown,
)
from quant.core.execution.manual_reconcile import (
    build_manual_reconciliation,
    render_manual_reconciliation_markdown,
    render_manual_validation_markdown,
    validate_manual_fills,
    write_manual_reconciliation_json,
    write_manual_reconciliation_markdown,
    write_manual_validation_json,
    write_manual_validation_markdown,
)
from quant.core.execution.refresh import ExecutionRefreshPaths, refresh_execution
from quant.core.execution.live_rehearsal import (
    build_live_rehearsal_report,
    render_live_rehearsal_markdown,
    write_live_rehearsal_json,
    write_live_rehearsal_markdown,
)
from quant.core.persistence.sqlite_store import SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare broker submission artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry_run = subparsers.add_parser("dry-run", help="Build a dry-run broker submission package.")
    dry_run.add_argument("--plan", required=True)
    dry_run.add_argument("--risk-guard", required=True)
    dry_run.add_argument("--adapter", default="dry_run")
    dry_run.add_argument("--output-json", default="research_store/reports/broker_submission.json")
    dry_run.add_argument("--output-md", default="research_store/reports/broker_submission.md")
    dry_run.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    dry_run.add_argument("--no-console", action="store_true")
    authorization = subparsers.add_parser(
        "authorization",
        help="Evaluate execution authorization for a broker submission package.",
    )
    authorization.add_argument("--submission", default="research_store/reports/broker_submission.json")
    authorization.add_argument("--policy", default=None)
    authorization.add_argument("--output-json", default="research_store/reports/execution_authorization.json")
    authorization.add_argument("--output-md", default="research_store/reports/execution_authorization.md")
    authorization.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    authorization.add_argument("--no-console", action="store_true")
    policy_create = subparsers.add_parser(
        "policy-create",
        help="Create an execution policy JSON/Markdown file.",
    )
    policy_create.add_argument("--mode", default="DRY_RUN", choices=["DRY_RUN", "LIVE"])
    policy_create.add_argument("--adapter", default="dry_run")
    policy_create.add_argument("--trade-date", default="")
    policy_create.add_argument("--strategy", default="")
    policy_create.add_argument("--approval-id", default="")
    policy_create.add_argument("--approved-by", default="")
    policy_create.add_argument("--expires-at", default="")
    policy_create.add_argument("--max-order-count", type=int, default=0)
    policy_create.add_argument("--max-notional", type=float, default=0.0)
    policy_create.add_argument("--auto-trade", action="store_true")
    policy_create.add_argument("--no-auto-trade", action="store_true")
    policy_create.add_argument("--output-json", default="config/execution_policy.generated.json")
    policy_create.add_argument("--output-md", default="config/execution_policy.generated.md")
    policy_create.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    policy_create.add_argument("--no-console", action="store_true")
    rehearsal = subparsers.add_parser(
        "live-rehearsal",
        help="Rehearse LIVE authorization behavior without submitting orders.",
    )
    rehearsal.add_argument("--submission", default="research_store/reports/broker_submission.json")
    rehearsal.add_argument("--adapter", default="qmt")
    rehearsal.add_argument("--policy", default=None)
    rehearsal.add_argument("--output-json", default="research_store/reports/live_rehearsal.json")
    rehearsal.add_argument("--output-md", default="research_store/reports/live_rehearsal.md")
    rehearsal.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    rehearsal.add_argument("--no-console", action="store_true")
    adapter_contract = subparsers.add_parser(
        "adapter-contract",
        help="Validate a broker submission against the broker adapter contract.",
    )
    adapter_contract.add_argument("--submission", default="research_store/reports/broker_submission.json")
    adapter_contract.add_argument("--authorization", default="research_store/reports/execution_authorization.json")
    adapter_contract.add_argument("--adapter", default="dry_run", choices=["dry_run", "qmt"])
    adapter_contract.add_argument("--submit", action="store_true")
    adapter_contract.add_argument("--output-json", default="research_store/reports/broker_adapter_contract.json")
    adapter_contract.add_argument("--output-md", default="research_store/reports/broker_adapter_contract.md")
    adapter_contract.add_argument("--no-console", action="store_true")
    audit_report = subparsers.add_parser(
        "audit-report",
        help="Render the latest execution refresh cycle from the execution audit JSONL.",
    )
    audit_report.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    audit_report.add_argument("--output-json", default="research_store/reports/execution_audit_report.json")
    audit_report.add_argument("--output-md", default="research_store/reports/execution_audit_report.md")
    audit_report.add_argument("--no-console", action="store_true")
    manual = subparsers.add_parser(
        "manual-package",
        help="Build manual order ticket and fill template from a dry-run submission.",
    )
    manual.add_argument("--submission", default="research_store/reports/broker_submission.json")
    manual.add_argument("--order-ticket", default="research_store/reports/manual_order_ticket.csv")
    manual.add_argument("--fill-template", default="research_store/reports/manual_fill_template.csv")
    manual.add_argument("--output-json", default="research_store/reports/manual_execution.json")
    manual.add_argument("--output-md", default="research_store/reports/manual_execution.md")
    manual.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    manual.add_argument("--no-console", action="store_true")
    manual_validate = subparsers.add_parser(
        "manual-validate",
        help="Validate a manually completed fill template against the order ticket.",
    )
    manual_validate.add_argument("--order-ticket", default="research_store/reports/manual_order_ticket.csv")
    manual_validate.add_argument("--fills", default="research_store/reports/manual_fill_template.csv")
    manual_validate.add_argument("--allow-incomplete", action="store_true")
    manual_validate.add_argument("--amount-tolerance", type=float, default=0.01)
    manual_validate.add_argument("--output-json", default="research_store/reports/manual_fill_validation.json")
    manual_validate.add_argument("--output-md", default="research_store/reports/manual_fill_validation.md")
    manual_validate.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    manual_validate.add_argument("--no-console", action="store_true")
    import_fills = subparsers.add_parser(
        "import-fills",
        help="Import broker/exported fill CSV rows into the manual fill template schema.",
    )
    import_fills.add_argument("--order-ticket", default="research_store/reports/manual_order_ticket.csv")
    import_fills.add_argument("--source", required=True)
    import_fills.add_argument("--output", default="research_store/reports/manual_fill_template.csv")
    import_fills.add_argument("--mapping-config", default=None)
    import_fills.add_argument("--report-json", default="research_store/reports/manual_fill_import.json")
    import_fills.add_argument("--report-md", default="research_store/reports/manual_fill_import.md")
    import_fills.add_argument("--validate", action="store_true")
    import_fills.add_argument("--validation-json", default="research_store/reports/manual_fill_validation.json")
    import_fills.add_argument("--validation-md", default="research_store/reports/manual_fill_validation.md")
    import_fills.add_argument("--amount-tolerance", type=float, default=0.01)
    import_fills.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    import_fills.add_argument("--no-console", action="store_true")
    manual_reconcile = subparsers.add_parser(
        "manual-reconcile",
        help="Validate manual fills and reconcile them against the order ticket.",
    )
    manual_reconcile.add_argument("--order-ticket", default="research_store/reports/manual_order_ticket.csv")
    manual_reconcile.add_argument("--fills", default="research_store/reports/manual_fill_template.csv")
    manual_reconcile.add_argument("--trade-date", required=True)
    manual_reconcile.add_argument("--account-id", default="paper")
    manual_reconcile.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    manual_reconcile.add_argument("--work-dir", default="research_store/reports")
    manual_reconcile.add_argument("--amount-tolerance", type=float, default=0.01)
    manual_reconcile.add_argument("--allow-incomplete", action="store_true")
    manual_reconcile.add_argument("--output-json", default="research_store/reports/manual_reconciliation.json")
    manual_reconcile.add_argument("--output-md", default="research_store/reports/manual_reconciliation.md")
    manual_reconcile.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    manual_reconcile.add_argument("--no-console", action="store_true")
    refresh = subparsers.add_parser(
        "refresh",
        help="Refresh the full local execution package without overwriting manual fills by default.",
    )
    refresh.add_argument("--paper-plan", default="research_store/reports/paper_plan.json")
    refresh.add_argument("--risk-guard", default="research_store/reports/risk_guard.json")
    refresh.add_argument("--submission", default="research_store/reports/broker_submission.json")
    refresh.add_argument("--policy", default="config/execution_policy.generated.json")
    refresh.add_argument("--execution-authorization-json", default="research_store/reports/execution_authorization.json")
    refresh.add_argument("--execution-authorization-md", default="research_store/reports/execution_authorization.md")
    refresh.add_argument("--broker-adapter-contract-json", default="research_store/reports/broker_adapter_contract.json")
    refresh.add_argument("--broker-adapter-contract-md", default="research_store/reports/broker_adapter_contract.md")
    refresh.add_argument("--manual-execution-json", default="research_store/reports/manual_execution.json")
    refresh.add_argument("--manual-execution-md", default="research_store/reports/manual_execution.md")
    refresh.add_argument("--order-ticket", default="research_store/reports/manual_order_ticket.csv")
    refresh.add_argument("--fill-template", default="research_store/reports/manual_fill_template.csv")
    refresh.add_argument("--pretrade-gate", default="research_store/reports/pretrade_gate.json")
    refresh.add_argument("--manual-fill-validation-json", default="research_store/reports/manual_fill_validation.json")
    refresh.add_argument("--manual-fill-validation-md", default="research_store/reports/manual_fill_validation.md")
    refresh.add_argument("--manual-reconciliation-json", default="research_store/reports/manual_reconciliation.json")
    refresh.add_argument("--manual-reconciliation-md", default="research_store/reports/manual_reconciliation.md")
    refresh.add_argument("--work-dir", default="research_store/reports")
    refresh.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    refresh.add_argument("--execution-day-end-json", default="research_store/reports/execution_day_end.json")
    refresh.add_argument("--execution-day-end-md", default="research_store/reports/execution_day_end.md")
    refresh.add_argument("--monitor-status", default="research_store/monitoring/status_summary.json")
    refresh.add_argument("--readiness", default="research_store/monitoring/readiness.json")
    refresh.add_argument("--stocks", default="research_store/sample/stocks.csv")
    refresh.add_argument("--bars", default="research_store/sample/daily_bar.cleaned.csv")
    refresh.add_argument("--daily-config", default="config/daily.yaml")
    refresh.add_argument("--cleaning-config", default="config/cleaning.yaml")
    refresh.add_argument("--risk-guard-control", default="research_store/state/risk_guard_control.env")
    refresh.add_argument("--monitor-history", default="research_store/monitoring/daily_history.csv")
    refresh.add_argument("--config-health-json", default="research_store/monitoring/config_health.json")
    refresh.add_argument("--config-health-md", default="research_store/monitoring/config_health.md")
    refresh.add_argument("--audit-log", default="research_store/reports/execution_audit.jsonl")
    refresh.add_argument("--audit-report-json", default="research_store/reports/execution_audit_report.json")
    refresh.add_argument("--audit-report-md", default="research_store/reports/execution_audit_report.md")
    refresh.add_argument("--dashboard-html", default="research_store/reports/execution_dashboard.html")
    refresh.add_argument("--account-id", default="paper")
    refresh.add_argument("--trade-date", default="")
    refresh.add_argument("--amount-tolerance", type=float, default=0.01)
    refresh.add_argument("--allow-incomplete", action="store_true")
    refresh.add_argument("--rebuild-manual-package", action="store_true")
    refresh.add_argument("--skip-reconciliation", action="store_true")
    refresh.add_argument("--fail-on-blocked", action="store_true")
    refresh.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "dry-run":
        package = build_dry_run_submission(
            plan_path=Path(args.plan),
            risk_guard_report_path=Path(args.risk_guard),
            adapter=args.adapter,
        )
        json_path = write_submission_json(package, Path(args.output_json))
        markdown_path = write_submission_markdown(package, Path(args.output_md))
        append_execution_audit(
            event_type="broker_dry_run",
            payload=package.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={"json": json_path, "markdown": markdown_path},
            summary={"adapter": package.adapter, "mode": package.mode},
        )
        if not args.no_console:
            print(render_submission_markdown(package))
        print(f"Wrote broker submission JSON to {json_path}")
        print(f"Wrote broker submission Markdown to {markdown_path}")
    if args.command == "authorization":
        report = build_execution_authorization_report(
            broker_submission_path=Path(args.submission),
            policy_path=Path(args.policy) if args.policy else None,
        )
        json_path = write_execution_authorization_json(report, Path(args.output_json))
        markdown_path = write_execution_authorization_markdown(report, Path(args.output_md))
        append_execution_audit(
            event_type="execution_authorization",
            payload=report.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={"json": json_path, "markdown": markdown_path, "policy": args.policy or ""},
            summary={"failed_checks": [check.name for check in report.checks if not check.passed]},
        )
        if not args.no_console:
            print(render_execution_authorization_markdown(report))
        print(f"Wrote execution authorization JSON to {json_path}")
        print(f"Wrote execution authorization Markdown to {markdown_path}")
        if not report.passed:
            raise SystemExit(2)
    if args.command == "policy-create":
        auto_trade = None
        if args.auto_trade:
            auto_trade = True
        if args.no_auto_trade:
            auto_trade = False
        policy = build_execution_policy(
            mode=args.mode,
            adapter=args.adapter,
            trade_date=args.trade_date,
            strategy_id=args.strategy,
            approval_id=args.approval_id,
            approved_by=args.approved_by,
            expires_at=args.expires_at,
            max_order_count=args.max_order_count,
            max_notional=args.max_notional,
            auto_trade_enabled=auto_trade,
        )
        json_path = write_execution_policy_json(policy, Path(args.output_json))
        markdown_path = write_execution_policy_markdown(policy, Path(args.output_md))
        append_execution_audit(
            event_type="execution_policy_created",
            payload=policy.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={"json": json_path, "markdown": markdown_path},
            status="READY",
            passed=True,
            summary={"allowed_modes": list(policy.allowed_modes), "allowed_adapters": list(policy.allowed_adapters)},
        )
        if not args.no_console:
            print(render_execution_policy_markdown(policy))
        print(f"Wrote execution policy JSON to {json_path}")
        print(f"Wrote execution policy Markdown to {markdown_path}")
    if args.command == "live-rehearsal":
        report = build_live_rehearsal_report(
            broker_submission_path=Path(args.submission),
            live_adapter=args.adapter,
            policy_path=Path(args.policy) if args.policy else None,
        )
        json_path = write_live_rehearsal_json(report, Path(args.output_json))
        markdown_path = write_live_rehearsal_markdown(report, Path(args.output_md))
        append_execution_audit(
            event_type="live_rehearsal",
            payload=report.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={"json": json_path, "markdown": markdown_path, "policy": args.policy or ""},
            passed=report.status in {"EXPECTED_BLOCK", "PASS", "POLICY_BLOCKED"},
            summary={"live_adapter": report.live_adapter},
        )
        if not args.no_console:
            print(render_live_rehearsal_markdown(report))
        print(f"Wrote live rehearsal JSON to {json_path}")
        print(f"Wrote live rehearsal Markdown to {markdown_path}")
    if args.command == "adapter-contract":
        report = build_broker_adapter_contract_report(
            adapter=_broker_adapter(args.adapter),
            submission=_read_json(Path(args.submission)),
            authorization=_read_json(Path(args.authorization)),
            submit=bool(args.submit),
        )
        json_path = write_broker_adapter_contract_json(report, Path(args.output_json))
        markdown_path = write_broker_adapter_contract_markdown(report, Path(args.output_md))
        if not args.no_console:
            print(render_broker_adapter_contract_markdown(report))
        print(f"Wrote broker adapter contract JSON to {json_path}")
        print(f"Wrote broker adapter contract Markdown to {markdown_path}")
        if not report.passed:
            raise SystemExit(2)
    if args.command == "audit-report":
        report = build_execution_audit_report(read_execution_audit_events(Path(args.audit_log)))
        json_path = write_execution_audit_report_json(report, Path(args.output_json))
        markdown_path = write_execution_audit_report_markdown(report, Path(args.output_md))
        if not args.no_console:
            print(render_execution_audit_report_markdown(report))
        print(f"Wrote execution audit report JSON to {json_path}")
        print(f"Wrote execution audit report Markdown to {markdown_path}")
    if args.command == "manual-package":
        package = build_manual_execution_package(
            broker_submission_path=Path(args.submission),
            order_ticket_path=Path(args.order_ticket),
            fill_template_path=Path(args.fill_template),
        )
        json_path = write_manual_execution_json(package, Path(args.output_json))
        markdown_path = write_manual_execution_markdown(package, Path(args.output_md))
        append_execution_audit(
            event_type="manual_package",
            payload=package.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={
                "json": json_path,
                "markdown": markdown_path,
                "order_ticket": args.order_ticket,
                "fill_template": args.fill_template,
            },
            summary={"package_id": package.package_id},
        )
        if not args.no_console:
            print(render_manual_execution_markdown(package))
        print(f"Wrote manual execution JSON to {json_path}")
        print(f"Wrote manual execution Markdown to {markdown_path}")
        print(f"Wrote manual order ticket CSV to {args.order_ticket}")
        print(f"Wrote manual fill template CSV to {args.fill_template}")
    if args.command == "manual-validate":
        report = validate_manual_fills(
            order_ticket_path=Path(args.order_ticket),
            fill_template_path=Path(args.fills),
            require_complete=not args.allow_incomplete,
            amount_tolerance=args.amount_tolerance,
        )
        json_path = write_manual_validation_json(report, Path(args.output_json))
        markdown_path = write_manual_validation_markdown(report, Path(args.output_md))
        append_execution_audit(
            event_type="manual_fill_validation",
            payload=report.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={
                "json": json_path,
                "markdown": markdown_path,
                "order_ticket": args.order_ticket,
                "fills": args.fills,
            },
            summary={"issue_count": len(report.issues), "allow_incomplete": bool(args.allow_incomplete)},
        )
        if not args.no_console:
            print(render_manual_validation_markdown(report))
        print(f"Wrote manual fill validation JSON to {json_path}")
        print(f"Wrote manual fill validation Markdown to {markdown_path}")
        if not report.passed:
            raise SystemExit(2)
    if args.command == "import-fills":
        report = import_manual_fills(
            order_ticket_path=Path(args.order_ticket),
            broker_fills_path=Path(args.source),
            output_path=Path(args.output),
            column_mapping=load_fill_column_mapping(Path(args.mapping_config)) if args.mapping_config else None,
        )
        json_path = write_manual_fill_import_json(report, Path(args.report_json))
        markdown_path = write_manual_fill_import_markdown(report, Path(args.report_md))
        append_execution_audit(
            event_type="manual_fill_import",
            payload=report.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={"json": json_path, "markdown": markdown_path, "output": args.output, "source": args.source},
            passed=report.passed,
            summary={"issues": len(report.issues), "matched": report.matched_count},
        )
        if not args.no_console:
            print(render_manual_fill_import_markdown(report))
        print(f"Wrote manual fill import JSON to {json_path}")
        print(f"Wrote manual fill import Markdown to {markdown_path}")
        print(f"Wrote manual fill template CSV to {args.output}")
        if args.validate:
            validation = validate_manual_fills(
                order_ticket_path=Path(args.order_ticket),
                fill_template_path=Path(args.output),
                amount_tolerance=args.amount_tolerance,
            )
            validation_json = write_manual_validation_json(validation, Path(args.validation_json))
            validation_md = write_manual_validation_markdown(validation, Path(args.validation_md))
            print(f"Wrote manual fill validation JSON to {validation_json}")
            print(f"Wrote manual fill validation Markdown to {validation_md}")
            if not validation.passed:
                raise SystemExit(2)
        if not report.passed:
            raise SystemExit(2)
    if args.command == "manual-reconcile":
        import pandas as pd

        trade_date = pd.to_datetime(args.trade_date).date()
        bundle = build_manual_reconciliation(
            order_ticket_path=Path(args.order_ticket),
            fill_template_path=Path(args.fills),
            trade_date=trade_date,
            account_id=args.account_id,
            output_dir=Path(args.work_dir),
            require_complete=not args.allow_incomplete,
            amount_tolerance=args.amount_tolerance,
        )
        store = SqliteStore(Path(args.sqlite))
        store.init_schema()
        store.save_trade_reconciliation_report(bundle.reconciliation)
        json_path = write_manual_reconciliation_json(bundle, Path(args.output_json))
        markdown_path = write_manual_reconciliation_markdown(bundle, Path(args.output_md))
        append_execution_audit(
            event_type="manual_reconciliation",
            payload=bundle.to_dict(),
            path=Path(args.audit_log),
            artifact_paths={
                "json": json_path,
                "markdown": markdown_path,
                "sqlite": args.sqlite,
                "local_orders": bundle.local_orders_path,
                "broker_orders": bundle.broker_orders_path,
                "broker_fills": bundle.broker_fills_path,
            },
            summary={"report_id": bundle.reconciliation.report_id},
        )
        if not args.no_console:
            print(render_manual_reconciliation_markdown(bundle))
        print(f"Wrote manual reconciliation JSON to {json_path}")
        print(f"Wrote manual reconciliation Markdown to {markdown_path}")
        print(f"Saved reconciliation audit trail to {args.sqlite}")
        if bundle.reconciliation.status != "OK":
            raise SystemExit(2)
    if args.command == "refresh":
        result = refresh_execution(
            ExecutionRefreshPaths(
                paper_plan=Path(args.paper_plan),
                risk_guard=Path(args.risk_guard),
                broker_submission=Path(args.submission),
                execution_policy=Path(args.policy),
                execution_authorization_json=Path(args.execution_authorization_json),
                execution_authorization_md=Path(args.execution_authorization_md),
                broker_adapter_contract_json=Path(args.broker_adapter_contract_json),
                broker_adapter_contract_md=Path(args.broker_adapter_contract_md),
                manual_execution_json=Path(args.manual_execution_json),
                manual_execution_md=Path(args.manual_execution_md),
                manual_order_ticket=Path(args.order_ticket),
                manual_fill_template=Path(args.fill_template),
                pretrade_gate=Path(args.pretrade_gate),
                manual_fill_validation_json=Path(args.manual_fill_validation_json),
                manual_fill_validation_md=Path(args.manual_fill_validation_md),
                manual_reconciliation_json=Path(args.manual_reconciliation_json),
                manual_reconciliation_md=Path(args.manual_reconciliation_md),
                manual_work_dir=Path(args.work_dir),
                paper_sqlite=Path(args.sqlite),
                execution_day_end_json=Path(args.execution_day_end_json),
                execution_day_end_md=Path(args.execution_day_end_md),
                monitor_status=Path(args.monitor_status),
                readiness=Path(args.readiness),
                stocks=Path(args.stocks),
                bars=Path(args.bars),
                daily_config=Path(args.daily_config),
                cleaning_config=Path(args.cleaning_config),
                risk_guard_control=Path(args.risk_guard_control),
                monitor_history=Path(args.monitor_history),
                config_health_json=Path(args.config_health_json),
                config_health_md=Path(args.config_health_md),
                audit_log=Path(args.audit_log),
                audit_report_json=Path(args.audit_report_json),
                audit_report_md=Path(args.audit_report_md),
                dashboard_html=Path(args.dashboard_html),
            ),
            account_id=args.account_id,
            trade_date_override=args.trade_date,
            amount_tolerance=args.amount_tolerance,
            allow_incomplete=bool(args.allow_incomplete),
            rebuild_manual_package=bool(args.rebuild_manual_package),
            run_reconciliation=not args.skip_reconciliation,
        )
        if not args.no_console:
            print(
                "Execution refresh: "
                f"status={result.status}, authorization={result.authorization_status}, "
                f"manual_validation={result.manual_validation_status}, "
                f"reconciliation={result.manual_reconciliation_status}, "
                f"day_end={result.day_end_status}, config={result.config_health_status}, "
                f"audit_report={result.audit_report_status}, dashboard={result.dashboard_status}"
            )
        print(f"Wrote execution refresh audit to {args.audit_log}")
        if args.fail_on_blocked and result.status == "BLOCKED":
            raise SystemExit(2)


def _broker_adapter(adapter: str):
    if adapter == "dry_run":
        return DryRunBrokerAdapter()
    if adapter == "qmt":
        return QmtBrokerAdapterSkeleton()
    raise ValueError(f"unsupported broker adapter: {adapter}")


def _read_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


if __name__ == "__main__":
    main()
