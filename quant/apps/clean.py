from __future__ import annotations

import argparse
from pathlib import Path

from quant.core.data.cleaning import (
    DailyBarCleaner,
    DailyBarCleaningPolicy,
    write_cleaning_markdown,
    write_cleaning_report,
)
from quant.core.data.repository import CsvDailyBarRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean market data files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    daily_bars = subparsers.add_parser("daily-bars", help="Clean daily_bar CSV data.")
    daily_bars.add_argument("--input", required=True)
    daily_bars.add_argument("--output", required=True)
    daily_bars.add_argument("--report", default="research_store/reports/data_cleaning.json")
    daily_bars.add_argument("--report-md", default="research_store/reports/data_cleaning.md")
    daily_bars.add_argument("--config", default=None)
    daily_bars.add_argument("--no-fix-ohlc-envelope", action="store_true")
    daily_bars.add_argument("--no-flag-zero-volume", action="store_true")
    daily_bars.add_argument("--no-flag-non-positive-price", action="store_true")
    daily_bars.add_argument("--flag-non-positive-amount", action="store_true")
    daily_bars.add_argument("--diff-sample-limit", type=int, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "daily-bars":
        bars = CsvDailyBarRepository(Path(args.input)).load()
        policy = _cleaning_policy_from_args(args)
        cleaned, report = DailyBarCleaner(policy).clean(bars)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(output, index=False)
        report_path = write_cleaning_report(report, Path(args.report))
        markdown_path = write_cleaning_markdown(report, Path(args.report_md))
        print(f"Wrote cleaned daily bars to {output}")
        print(f"Wrote cleaning report to {report_path}")
        print(f"Wrote cleaning Markdown to {markdown_path}")
        print(report.to_dict())


def _cleaning_policy_from_args(args: argparse.Namespace) -> DailyBarCleaningPolicy:
    policy = (
        DailyBarCleaningPolicy.from_file(Path(args.config))
        if args.config
        else DailyBarCleaningPolicy()
    )
    return policy.merge(
        {
            "fix_ohlc_envelope": False if args.no_fix_ohlc_envelope else None,
            "flag_zero_volume": False if args.no_flag_zero_volume else None,
            "flag_non_positive_price": False if args.no_flag_non_positive_price else None,
            "flag_non_positive_amount": True if args.flag_non_positive_amount else None,
            "diff_sample_limit": args.diff_sample_limit,
        }
    )


if __name__ == "__main__":
    main()
