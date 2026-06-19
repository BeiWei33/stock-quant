from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant.core.backtest.engine import BacktestEngine, BacktestRequest
from quant.core.data.repository import CsvDailyBarRepository, CsvStockRepository
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.strategy.momentum import MomentumRankStrategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local momentum backtest.")
    parser.add_argument("--bars", help="CSV file containing daily_bar rows.")
    parser.add_argument("--stocks", help="CSV file containing stock master rows.")
    parser.add_argument("--benchmark-bars", help="Optional CSV file containing benchmark_bar rows.")
    parser.add_argument("--benchmark-code", default="equal_weight")
    parser.add_argument("--sqlite", help="SQLite store containing stocks and daily_bar tables.")
    parser.add_argument("--start-date", help="Backtest start date.")
    parser.add_argument("--end-date", help="Backtest end date.")
    parser.add_argument("--output", default="research_store/reports/backtest.json")
    parser.add_argument("--output-md")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    parser.add_argument("--rebalance", choices=["weekly", "monthly"], default="weekly")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.sqlite:
        store = SqliteStore(Path(args.sqlite))
        bars = store.load_daily_bars(
            start_date=_parse_date(args.start_date),
            end_date=_parse_date(args.end_date),
            adj_type="qfq",
        )
        if bars.empty:
            bars = store.load_daily_bars(
                start_date=_parse_date(args.start_date),
                end_date=_parse_date(args.end_date),
            )
        stocks = store.load_stocks()
        benchmark_bars = store.load_benchmark_bars(args.benchmark_code)
    else:
        if not args.bars or not args.stocks:
            raise ValueError("either --sqlite or both --bars and --stocks are required")
        bars = CsvDailyBarRepository(Path(args.bars)).load()
        bars = _filter_bars(bars, args.start_date, args.end_date)
        stocks = CsvStockRepository(Path(args.stocks)).load()
        benchmark_bars = _load_benchmark_bars(args.benchmark_bars, args.benchmark_code)
    if bars.empty:
        raise ValueError("backtest has no daily bars in the selected date range")
    if stocks.empty:
        raise ValueError("backtest has no stocks")

    engine = BacktestEngine()
    result = engine.run(
        BacktestRequest(
            bars=bars,
            stocks=stocks,
            strategy=MomentumRankStrategy(),
            benchmark_bars=benchmark_bars,
            benchmark_code=args.benchmark_code,
            initial_cash=args.initial_cash,
            rebalance=args.rebalance,
        )
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "benchmark_code": result.benchmark_code,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "strategy": _strategy_record(result.strategy_registration),
        "metrics": result.metrics,
        "returns": _series_records(result.returns, "strategy_return"),
        "benchmark_returns": _series_records(result.benchmark_returns, "benchmark_return"),
        "active_returns": _series_records(result.active_returns, "active_return"),
        "equity_curve": _series_records(result.equity_curve, "strategy_equity"),
        "benchmark_equity_curve": _series_records(
            result.benchmark_equity_curve, "benchmark_equity"
        ),
        "rebalance_records": [record.to_dict() for record in result.rebalance_records],
        "snapshots": [snapshot.to_dict() for snapshot in result.snapshots],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        markdown = _render_markdown_report(
            result.metrics,
            args.rebalance,
            result.benchmark_code,
            _strategy_record(result.strategy_registration),
        )
        markdown_output = Path(args.output_md)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown, encoding="utf-8")
    print(f"Wrote backtest report to {output}")
    if args.output_md:
        print(f"Wrote backtest Markdown report to {args.output_md}")


def _series_records(series, value_name: str) -> list[dict[str, object]]:
    records = []
    for index, value in series.items():
        trade_date = index.isoformat() if hasattr(index, "isoformat") else str(index)
        records.append({"trade_date": trade_date, value_name: float(value)})
    return records


def _strategy_record(registration) -> dict[str, object]:
    return {
        "strategy_id": registration.strategy_id,
        "strategy_version": registration.strategy_version,
        "status": registration.status,
        "factor_set_id": registration.factor_set_id,
        "research_report_path": registration.research_report_path,
        "code_hash": registration.code_hash,
        "config_hash": registration.config_hash,
        "config_json": registration.config_json,
    }


def _load_benchmark_bars(path: str | None, benchmark_code: str):
    if not path:
        return None
    import pandas as pd

    df = pd.read_csv(path)
    if "benchmark_code" not in df.columns:
        df["benchmark_code"] = benchmark_code
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _parse_date(value: str | None):
    if not value:
        return None
    import pandas as pd

    return pd.to_datetime(value).date()


def _filter_bars(bars, start_date: str | None, end_date: str | None):
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start is not None:
        bars = bars[bars["trade_date"] >= start]
    if end is not None:
        bars = bars[bars["trade_date"] <= end]
    return bars.reset_index(drop=True)


def _render_markdown_report(
    metrics: dict[str, object],
    rebalance: str,
    benchmark_code: str,
    strategy: dict[str, object],
) -> str:
    rows = [
        ["策略", strategy["strategy_id"]],
        ["策略版本", strategy["strategy_version"]],
        ["策略配置哈希", str(strategy["config_hash"])[:12]],
        ["调仓频率", rebalance],
        ["基准", benchmark_code],
        ["总收益", _percent(metrics.get("total_return", 0.0))],
        ["基准总收益", _percent(metrics.get("benchmark_total_return", 0.0))],
        ["超额收益", _percent(metrics.get("excess_return", 0.0))],
        ["年化收益", _percent(metrics.get("annual_return", 0.0))],
        ["基准年化收益", _percent(metrics.get("benchmark_annual_return", 0.0))],
        ["年化波动", _percent(metrics.get("volatility", 0.0))],
        ["基准年化波动", _percent(metrics.get("benchmark_volatility", 0.0))],
        ["夏普比率", _decimal(metrics.get("sharpe", 0.0))],
        ["信息比率", _decimal(metrics.get("information_ratio", 0.0))],
        ["跟踪误差", _percent(metrics.get("tracking_error", 0.0))],
        ["超额胜率", _percent(metrics.get("active_win_rate", 0.0))],
        ["最大回撤", _percent(metrics.get("max_drawdown", 0.0))],
        ["Beta", _decimal(metrics.get("beta", 0.0))],
        ["基准相关性", _decimal(metrics.get("benchmark_correlation", 0.0))],
        ["调仓次数", _integer(metrics.get("rebalance_count", 0.0))],
        ["被拒调仓次数", _integer(metrics.get("rejected_rebalance_count", 0.0))],
        ["成交订单数", _integer(metrics.get("filled_order_count", 0.0))],
        ["拒绝订单数", _integer(metrics.get("rejected_order_count", 0.0))],
        ["平均换手", _percent(metrics.get("average_turnover", 0.0))],
        ["最大换手", _percent(metrics.get("max_turnover", 0.0))],
    ]
    return "\n".join(
        [
            "# 回测报告",
            "",
            _table(["指标", "数值"], rows),
            "",
        ]
    )


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _decimal(value: float) -> str:
    return f"{value:.4f}"


def _integer(value: float) -> str:
    return str(int(value))


if __name__ == "__main__":
    main()
