from __future__ import annotations

import argparse
from pathlib import Path

from quant.core.monitoring.notification import (
    DailyNotificationBuilder,
    FileNotificationSink,
    render_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send local operational notifications.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    daily = subparsers.add_parser("daily", help="Build a notification from daily_summary.json.")
    daily.add_argument("--summary", default="research_store/reports/daily_summary.json")
    daily.add_argument("--report-md", default="research_store/reports/daily_report.md")
    daily.add_argument("--report-html", default="research_store/reports/daily_report.html")
    daily.add_argument("--output", default="research_store/reports/daily_notification.json")
    daily.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "daily":
        message = DailyNotificationBuilder(
            summary_path=Path(args.summary),
            report_markdown_path=Path(args.report_md) if args.report_md else None,
            report_html_path=Path(args.report_html) if args.report_html else None,
        ).build()
        output_path = FileNotificationSink(Path(args.output)).send(message)
        if not args.no_console:
            print(render_text(message))
        print(f"Wrote notification payload to {output_path}")


if __name__ == "__main__":
    main()
