from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from quant.core.collector.akshare_source import (
    DEFAULT_A_SHARE_SYMBOLS,
    AkShareDataSource,
    AkShareDataSourceConfig,
)
from quant.core.collector.base import MarketDataSource
from quant.core.collector.baidu_source import BaiduDataSource, BaiduDataSourceConfig
from quant.core.collector.csv_source import CsvDataSource, CsvDataSourceConfig
from quant.core.collector.fallback_source import FallbackMarketDataSource, LazyMarketDataSource
from quant.core.collector.mootdx_source import MootdxDataSource, MootdxDataSourceConfig
from quant.core.collector.tencent_source import TencentDataSource, TencentDataSourceConfig
from quant.core.collector.tushare_source import TushareDataSource
from quant.core.persistence.sqlite_store import SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect market data into the local store.")
    parser.add_argument(
        "--source",
        choices=["csv", "auto", "mootdx", "tencent", "baidu", "akshare", "tushare"],
        default="csv",
    )
    parser.add_argument("--sqlite", default="research_store/market_data.sqlite3")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--stocks")
    parser.add_argument("--bars")
    parser.add_argument("--benchmark-bars")
    parser.add_argument("--benchmark-code", default="equal_weight")
    parser.add_argument("--akshare-symbols", help="Comma-separated A-share symbols for AkShare.")
    parser.add_argument("--akshare-symbols-file", help="Text file with one AkShare symbol per line.")
    parser.add_argument("--akshare-limit", type=int, help="Limit AkShare collection to the first N symbols.")
    parser.add_argument("--akshare-all", action="store_true", help="Collect the full AkShare A-share universe.")
    parser.add_argument("--tushare-token")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    source = _build_source(args)
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    result = source.collect(start_date=start_date, end_date=end_date)

    store = SqliteStore(Path(args.sqlite))
    store.init_schema()
    store.save_stocks(result.stocks)
    store.save_daily_bars(result.daily_bars)
    store.save_benchmark_bars(result.benchmark_bars)

    print(
        "Collected "
        f"stocks={len(result.stocks)} "
        f"daily_bars={len(result.daily_bars)} "
        f"benchmark_bars={len(result.benchmark_bars)} "
        f"into {args.sqlite}"
    )
    if hasattr(source, "attempts"):
        for attempt in getattr(source, "attempts", []):
            detail = f": {attempt.error}" if attempt.error else ""
            print(f"Source attempt {attempt.source_name}: {attempt.status}{detail}")


def _build_source(args: argparse.Namespace) -> MarketDataSource:
    if args.source == "csv":
        if not args.stocks or not args.bars:
            raise ValueError("--stocks and --bars are required for csv collection")
        return CsvDataSource(
            CsvDataSourceConfig(
                stocks_path=Path(args.stocks),
                daily_bars_path=Path(args.bars),
                benchmark_bars_path=Path(args.benchmark_bars) if args.benchmark_bars else None,
                benchmark_code=args.benchmark_code,
            )
        )
    if args.source == "akshare":
        return AkShareDataSource(
            AkShareDataSourceConfig(
                symbols=_akshare_symbols(args) or DEFAULT_A_SHARE_SYMBOLS,
                max_symbols=args.akshare_limit,
                all_market=bool(args.akshare_all),
            )
        )
    if args.source == "mootdx":
        return MootdxDataSource(
            MootdxDataSourceConfig(
                symbols=_akshare_symbols(args) or DEFAULT_A_SHARE_SYMBOLS,
                max_symbols=args.akshare_limit,
                all_market=bool(args.akshare_all),
            )
        )
    if args.source == "tencent":
        return TencentDataSource(
            TencentDataSourceConfig(
                symbols=_akshare_symbols(args) or DEFAULT_A_SHARE_SYMBOLS,
                max_symbols=args.akshare_limit,
                all_market=bool(args.akshare_all),
            )
        )
    if args.source == "baidu":
        return BaiduDataSource(
            BaiduDataSourceConfig(
                symbols=_akshare_symbols(args) or DEFAULT_A_SHARE_SYMBOLS,
                max_symbols=args.akshare_limit,
                all_market=bool(args.akshare_all),
            )
        )
    if args.source == "tushare":
        token = args.tushare_token or ""
        return TushareDataSource(token=token)
    if args.source == "auto":
        return FallbackMarketDataSource(_auto_sources(args))
    raise ValueError(f"unsupported source: {args.source}")


def _auto_sources(args: argparse.Namespace) -> list[MarketDataSource]:
    symbols = _akshare_symbols(args) or DEFAULT_A_SHARE_SYMBOLS
    sources: list[MarketDataSource] = [
        LazyMarketDataSource(
            "mootdx",
            lambda: MootdxDataSource(
                MootdxDataSourceConfig(
                    symbols=symbols,
                    max_symbols=args.akshare_limit,
                    all_market=bool(args.akshare_all),
                )
            ),
        ),
        TencentDataSource(
            TencentDataSourceConfig(
                symbols=symbols,
                max_symbols=args.akshare_limit,
                all_market=bool(args.akshare_all),
            )
        ),
        BaiduDataSource(
            BaiduDataSourceConfig(
                symbols=symbols,
                max_symbols=args.akshare_limit,
                all_market=bool(args.akshare_all),
            )
        ),
    ]
    if args.tushare_token:
        sources.append(
            LazyMarketDataSource(
                "tushare",
                lambda: TushareDataSource(token=args.tushare_token or ""),
            )
        )
    sources.append(
        LazyMarketDataSource(
            "akshare",
            lambda: AkShareDataSource(
                AkShareDataSourceConfig(
                    symbols=symbols,
                    max_symbols=args.akshare_limit,
                    all_market=bool(args.akshare_all),
                )
            ),
        )
    )
    return sources


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return pd.to_datetime(value).date()


def _akshare_symbols(args: argparse.Namespace) -> tuple[str, ...]:
    symbols: list[str] = []
    if args.akshare_symbols_file:
        path = Path(args.akshare_symbols_file)
        symbols.extend(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    if args.akshare_symbols:
        symbols.extend(part.strip() for part in args.akshare_symbols.split(",") if part.strip())
    return tuple(symbols)


if __name__ == "__main__":
    main()
