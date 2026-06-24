from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant.core.backtest.engine import BacktestEngine, BacktestRequest
from quant.core.backtest.multi_strategy import MultiStrategyBacktestEngine, MultiStrategyBacktestRequest
from quant.core.capital_allocation import AllocationConfig
from quant.core.data.repository import CsvDailyBarRepository, CsvStockRepository
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.strategy.factory import build_strategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local strategy backtest.")
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
    parser.add_argument("--strategy", default="momentum_rank")
    parser.add_argument("--universe", choices=["all", "csi300", "csi500", "csi800"], default="all",
                        help="Stock universe filter")
    parser.add_argument(
        "--multi-strategy",
        help="Comma-separated strategy ids, for example: momentum_rank,quality_rank.",
    )
    parser.add_argument("--allocation-method", choices=["equal", "risk_parity"], default="risk_parity")
    parser.add_argument("--allocation-lookback-days", type=int, default=60)
    parser.add_argument("--target-volatility", type=float)
    parser.add_argument("--max-strategy-weight", type=float, default=0.60)
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

        # Apply universe filter
        if args.universe and args.universe != "all":
            bars = _filter_by_universe(bars, args.universe)
            print(f"[Universe] Filtered to {args.universe}: {bars['ts_code'].nunique()} stocks")
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

    if args.multi_strategy:
        strategies = [build_strategy(name.strip()) for name in args.multi_strategy.split(",") if name.strip()]
        result = MultiStrategyBacktestEngine().run(
            MultiStrategyBacktestRequest(
                bars=bars,
                stocks=stocks,
                strategies=strategies,
                allocation_config=AllocationConfig(
                    method=args.allocation_method,
                    lookback_days=args.allocation_lookback_days,
                    target_volatility=args.target_volatility,
                    max_strategy_weight=args.max_strategy_weight,
                ),
                benchmark_bars=benchmark_bars,
                benchmark_code=args.benchmark_code,
                initial_cash=args.initial_cash,
                rebalance=args.rebalance,
            )
        )
        payload = _multi_strategy_payload(result, args)
    else:
        engine = BacktestEngine()
        result = engine.run(
            BacktestRequest(
                bars=bars,
                stocks=stocks,
                strategy=build_strategy(args.strategy),
                benchmark_bars=benchmark_bars,
                benchmark_code=args.benchmark_code,
                initial_cash=args.initial_cash,
                rebalance=args.rebalance,
            )
        )
        payload = _single_strategy_payload(result, args)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        if args.multi_strategy:
            markdown = _render_multi_strategy_markdown_report(payload)
        else:
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


def _single_strategy_payload(result, args) -> dict[str, object]:
    return {
        "mode": "single_strategy",
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


def _multi_strategy_payload(result, args) -> dict[str, object]:
    strategy_returns = _frame_records(result.strategy_returns)
    allocation_records = [record.to_dict() for record in result.allocation_records]
    return {
        "mode": "multi_strategy",
        "benchmark_code": args.benchmark_code,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "strategies": list(result.strategy_results.keys()),
        "allocation": {
            "method": args.allocation_method,
            "lookback_days": args.allocation_lookback_days,
            "target_volatility": args.target_volatility,
            "max_strategy_weight": args.max_strategy_weight,
        },
        "metrics": result.metrics,
        "returns": _series_records(result.portfolio_returns, "portfolio_return"),
        "benchmark_returns": _series_records(result.benchmark_returns, "benchmark_return"),
        "active_returns": _series_records(result.active_returns, "active_return"),
        "equity_curve": _series_records(result.equity_curve, "portfolio_equity"),
        "benchmark_equity_curve": _series_records(
            result.benchmark_equity_curve, "benchmark_equity"
        ),
        "strategy_returns": strategy_returns,
        "strategy_summary": _strategy_return_summary(strategy_returns),
        "allocation_history": _frame_records(result.allocation_history),
        "allocation_records": allocation_records,
        "latest_allocation": _latest_allocation(allocation_records),
    }


def _series_records(series, value_name: str) -> list[dict[str, object]]:
    records = []
    for index, value in series.items():
        trade_date = index.isoformat() if hasattr(index, "isoformat") else str(index)
        records.append({"trade_date": trade_date, value_name: float(value)})
    return records


def _frame_records(frame) -> list[dict[str, object]]:
    records = []
    if "trade_date" in frame.columns:
        raw_records = frame.to_dict(orient="records")
    else:
        indexed = frame.copy()
        indexed.index.name = indexed.index.name or "trade_date"
        raw_records = indexed.reset_index().to_dict(orient="records")
    for row in raw_records:
        normalized = {}
        for key, value in row.items():
            if hasattr(value, "isoformat"):
                normalized[str(key)] = value.isoformat()
            else:
                normalized[str(key)] = value
        records.append(normalized)
    return records


def _strategy_return_summary(records: list[dict[str, object]]) -> list[dict[str, object]]:
    strategy_ids = sorted(
        {
            str(key)
            for record in records
            for key in record
            if key not in {"trade_date", "index"}
        }
    )
    summary = []
    for strategy_id in strategy_ids:
        values = [float(record.get(strategy_id, 0.0) or 0.0) for record in records]
        cumulative = 1.0
        positive_days = 0
        for value in values:
            cumulative *= 1.0 + value
            if value > 0:
                positive_days += 1
        summary.append(
            {
                "strategy_id": strategy_id,
                "cumulative_return": cumulative - 1.0,
                "latest_return": values[-1] if values else 0.0,
                "positive_day_ratio": positive_days / len(values) if values else 0.0,
            }
        )
    return summary


def _latest_allocation(records: list[dict[str, object]]) -> list[dict[str, object]]:
    if not records:
        return []
    weights = records[-1].get("weights", [])
    if not isinstance(weights, list):
        return []
    normalized = []
    for item in weights:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "strategy_id": str(item.get("strategy_id", "")),
                "capital_weight": float(item.get("capital_weight", 0.0) or 0.0),
                "is_cash": bool(item.get("is_cash", False)),
            }
        )
    return sorted(normalized, key=lambda row: (row["is_cash"], row["strategy_id"]))


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


def _filter_by_universe(bars, universe: str):
    """Filter bars by stock universe (csi300/csi500/csi800)."""
    import akshare as ak

    # Get index components
    csi300_codes = set()
    csi500_codes = set()

    if universe in ["csi300", "csi800"]:
        try:
            df = ak.index_stock_cons(symbol="000300")
            for code in df["品种代码"]:
                if code.startswith("6"):
                    csi300_codes.add(f"{code}.SH")
                else:
                    csi300_codes.add(f"{code}.SZ")
        except Exception as e:
            print(f"[Warning] Failed to get CSI 300 components: {e}")

    if universe in ["csi500", "csi800"]:
        try:
            df = ak.index_stock_cons(symbol="000905")
            for code in df["品种代码"]:
                if code.startswith("6"):
                    csi500_codes.add(f"{code}.SH")
                else:
                    csi500_codes.add(f"{code}.SZ")
        except Exception as e:
            print(f"[Warning] Failed to get CSI 500 components: {e}")

    # Combine codes
    if universe == "csi300":
        valid_codes = csi300_codes
    elif universe == "csi500":
        valid_codes = csi500_codes
    elif universe == "csi800":
        valid_codes = csi300_codes | csi500_codes
    else:
        return bars

    if not valid_codes:
        print(f"[Warning] No stock codes found for {universe}, using all stocks")
        return bars

    # Filter bars
    filtered = bars[bars["ts_code"].isin(valid_codes)]
    return filtered.reset_index(drop=True)


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


def _render_multi_strategy_markdown_report(payload: dict[str, object]) -> str:
    metrics = payload["metrics"]
    allocation = payload["allocation"]
    rows = [
        ["策略组合", ", ".join(payload["strategies"])],
        ["资金分配方法", allocation["method"]],
        ["回看天数", allocation["lookback_days"]],
        [
            "目标波动率",
            "-" if allocation["target_volatility"] is None else _percent(allocation["target_volatility"]),
        ],
        ["单策略上限", _percent(allocation["max_strategy_weight"])],
        ["总收益", _percent(metrics.get("total_return", 0.0))],
        ["基准总收益", _percent(metrics.get("benchmark_total_return", 0.0))],
        ["超额收益", _percent(metrics.get("excess_return", 0.0))],
        ["年化收益", _percent(metrics.get("annual_return", 0.0))],
        ["年化波动", _percent(metrics.get("volatility", 0.0))],
        ["夏普比率", _decimal(metrics.get("sharpe", 0.0))],
        ["最大回撤", _percent(metrics.get("max_drawdown", 0.0))],
        ["平均现金权重", _percent(metrics.get("average_cash_weight", 0.0))],
    ]
    return "\n".join(
        [
            "# 多策略组合回测报告",
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


def _render_multi_strategy_markdown_report(payload: dict[str, object]) -> str:  # type: ignore[no-redef]
    metrics = payload["metrics"]
    allocation = payload["allocation"]
    overview_rows = [
        ["策略组合", ", ".join(payload["strategies"])],
        ["资金分配方法", allocation["method"]],
        ["回看天数", allocation["lookback_days"]],
        [
            "目标波动率",
            "-" if allocation["target_volatility"] is None else _percent(allocation["target_volatility"]),
        ],
        ["单策略上限", _percent(allocation["max_strategy_weight"])],
        ["总收益", _percent(metrics.get("total_return", 0.0))],
        ["基准总收益", _percent(metrics.get("benchmark_total_return", 0.0))],
        ["超额收益", _percent(metrics.get("excess_return", 0.0))],
        ["年化收益", _percent(metrics.get("annual_return", 0.0))],
        ["年化波动", _percent(metrics.get("volatility", 0.0))],
        ["夏普比率", _decimal(metrics.get("sharpe", 0.0))],
        ["最大回撤", _percent(metrics.get("max_drawdown", 0.0))],
        ["平均现金权重", _percent(metrics.get("average_cash_weight", 0.0))],
    ]
    strategy_rows = [
        [
            item["strategy_id"],
            _percent(item["cumulative_return"]),
            _percent(item["latest_return"]),
            _percent(item["positive_day_ratio"]),
        ]
        for item in payload.get("strategy_summary", [])
    ]
    allocation_rows = [
        [
            item["strategy_id"],
            _percent(item["capital_weight"]),
            "是" if item["is_cash"] else "否",
        ]
        for item in payload.get("latest_allocation", [])
    ]
    cash_rows = [
        [
            row.get("trade_date", "-"),
            _percent(row.get("allocated_weight", 0.0)),
            _percent(row.get("cash_weight", 0.0)),
        ]
        for row in payload.get("allocation_history", [])[-10:]
    ]
    return "\n".join(
        [
            "# 多策略组合回测报告",
            "",
            "## 组合指标",
            "",
            _table(["指标", "数值"], overview_rows),
            "",
            "## 策略收益拆解",
            "",
            _table(["策略", "累计收益", "最近日收益", "胜率"], strategy_rows),
            "",
            "## 资金权重变化",
            "",
            _table(["策略/现金", "最新权重", "是否现金"], allocation_rows),
            "",
            "## 现金仓位",
            "",
            _table(["日期", "策略仓位", "现金权重"], cash_rows),
            "",
        ]
    )


if __name__ == "__main__":
    main()
