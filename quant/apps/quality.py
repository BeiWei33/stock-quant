from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from quant.core.data.quality import (
    DataQualityAnalyzer,
    render_quality_markdown,
    write_quality_json,
    write_quality_markdown,
)
from quant.core.data.repository import CsvDailyBarRepository, CsvStockRepository
from quant.core.persistence.sqlite_store import SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate market data quality reports.")
    parser.add_argument("--sqlite", help="SQLite store containing stocks and daily_bar tables.")
    parser.add_argument("--bars", help="CSV file containing daily_bar rows.")
    parser.add_argument("--stocks", help="Optional CSV file containing stock master rows.")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--adj-type", default="qfq")
    parser.add_argument("--no-weekday-gaps", action="store_true")
    parser.add_argument("--output-json", default="research_store/reports/data_quality.json")
    parser.add_argument("--output-md", default="research_store/reports/data_quality.md")
    parser.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bars, stocks = _load_inputs(args)
    report = DataQualityAnalyzer(check_weekday_gaps=not args.no_weekday_gaps).analyze(
        bars=bars,
        stocks=stocks,
    )
    json_path = write_quality_json(report, Path(args.output_json))
    markdown_path = write_quality_markdown(report, Path(args.output_md))
    if not args.no_console:
        print(render_quality_markdown(report))
    print(f"Wrote data quality JSON to {json_path}")
    print(f"Wrote data quality Markdown to {markdown_path}")


def _load_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    if args.sqlite:
        store = SqliteStore(Path(args.sqlite))
        bars = store.load_daily_bars(start_date=start_date, end_date=end_date, adj_type=args.adj_type)
        stocks = store.load_stocks()
        return bars, stocks
    if not args.bars:
        raise ValueError("either --sqlite or --bars is required")
    bars = CsvDailyBarRepository(Path(args.bars)).load()
    if start_date is not None:
        bars = bars[bars["trade_date"] >= start_date]
    if end_date is not None:
        bars = bars[bars["trade_date"] <= end_date]
    stocks = CsvStockRepository(Path(args.stocks)).load() if args.stocks else pd.DataFrame()
    return bars.reset_index(drop=True), stocks


def _parse_date(value: str | None):
    if value is None:
        return None
    return pd.to_datetime(value).date()


if __name__ == "__main__":
    main()
