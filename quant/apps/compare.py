from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from quant.core.reconciliation.backtest_paper import (
    compare_backtest_to_paper,
    render_diff_markdown,
    write_diff_json,
    write_diff_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare quant workflow artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backtest_paper = subparsers.add_parser(
        "backtest-paper", help="Compare backtest target weights with paper account state."
    )
    backtest_paper.add_argument("--backtest", required=True)
    backtest_paper.add_argument("--paper-sqlite", default="research_store/paper_trading.sqlite3")
    backtest_paper.add_argument("--trade-date", required=True)
    backtest_paper.add_argument("--account-id", default="paper")
    backtest_paper.add_argument("--tolerance", type=float, default=0.02)
    backtest_paper.add_argument("--output-json", default="research_store/reports/backtest_paper_diff.json")
    backtest_paper.add_argument("--output-md", default="research_store/reports/backtest_paper_diff.md")
    backtest_paper.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "backtest-paper":
        report = compare_backtest_to_paper(
            backtest_report_path=Path(args.backtest),
            paper_store_path=Path(args.paper_sqlite),
            trade_date=pd.to_datetime(args.trade_date).date(),
            account_id=args.account_id,
            tolerance=args.tolerance,
        )
        json_path = write_diff_json(report, Path(args.output_json))
        markdown_path = write_diff_markdown(report, Path(args.output_md))
        if not args.no_console:
            print(render_diff_markdown(report))
        print(f"Wrote backtest-paper diff JSON to {json_path}")
        print(f"Wrote backtest-paper diff Markdown to {markdown_path}")


if __name__ == "__main__":
    main()
