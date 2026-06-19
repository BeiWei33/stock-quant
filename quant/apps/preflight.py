from __future__ import annotations

import argparse
from pathlib import Path

from quant.core.execution.preflight import (
    build_pretrade_gate_report,
    render_pretrade_gate_markdown,
    write_pretrade_gate_json,
    write_pretrade_gate_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pre-trade gate checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Validate monitor, risk guard, and broker artifacts.")
    check.add_argument("--monitor-status", default="research_store/monitoring/status_summary.json")
    check.add_argument("--risk-guard", default="research_store/reports/risk_guard.json")
    check.add_argument("--broker-submission", default="research_store/reports/broker_submission.json")
    check.add_argument("--execution-policy", default=None)
    check.add_argument("--output-json", default="research_store/reports/pretrade_gate.json")
    check.add_argument("--output-md", default="research_store/reports/pretrade_gate.md")
    check.add_argument("--allow-monitor-warning", action="store_true")
    check.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "check":
        report = build_pretrade_gate_report(
            monitor_status_path=Path(args.monitor_status),
            risk_guard_path=Path(args.risk_guard),
            broker_submission_path=Path(args.broker_submission),
            execution_policy_path=Path(args.execution_policy) if args.execution_policy else None,
            allow_monitor_warning=args.allow_monitor_warning,
        )
        json_path = write_pretrade_gate_json(report, Path(args.output_json))
        markdown_path = write_pretrade_gate_markdown(report, Path(args.output_md))
        if not args.no_console:
            print(render_pretrade_gate_markdown(report))
        print(f"Wrote pre-trade gate JSON to {json_path}")
        print(f"Wrote pre-trade gate Markdown to {markdown_path}")
        if not report.passed:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
