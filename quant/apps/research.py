from __future__ import annotations

import argparse
from pathlib import Path

from quant.core.data.repository import CsvDailyBarRepository
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.research.alpha_validation import validate_factor
from quant.core.research.factor_factory import build_factor
from quant.core.research.report import AlphaResearchReportWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run alpha validation for a factor.")
    parser.add_argument("--bars", help="CSV file containing daily_bar rows.")
    parser.add_argument("--sqlite", help="SQLite store containing daily_bar table.")
    parser.add_argument("--factor", default="momentum_60d")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--quantiles", type=int, default=5)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--output-dir", default="research_store/reports/alpha")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.sqlite:
        store = SqliteStore(Path(args.sqlite))
        bars = store.load_daily_bars(adj_type="qfq")
        if bars.empty:
            bars = store.load_daily_bars()
    else:
        if not args.bars:
            raise ValueError("either --sqlite or --bars is required")
        bars = CsvDailyBarRepository(Path(args.bars)).load()

    factor = build_factor(args.factor)
    factor_values = factor.calculate(bars)
    result = validate_factor(
        bars=bars,
        factor_values=factor_values,
        factor_name=factor.name,
        horizon=args.horizon,
        quantiles=args.quantiles,
        train_ratio=args.train_ratio,
    )
    paths = AlphaResearchReportWriter().write(result, Path(args.output_dir))
    print(f"Wrote alpha JSON report to {paths.json_path}")
    print(f"Wrote alpha Markdown report to {paths.markdown_path}")


if __name__ == "__main__":
    main()
