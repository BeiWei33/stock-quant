from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from quant.core.data.repository import CsvDailyBarRepository, CsvStockRepository
from quant.core.models import OrderRiskResult, RiskDecision
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.strategy.admission import StrategyAdmissionPolicy
from quant.core.strategy.factory import build_strategy
from quant.core.trader.paper import PaperTradingEngine
from quant.core.trader.simulator import PaperExecutionSimulator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a paper-trading rebalance plan.")
    parser.add_argument("--bars", help="CSV file containing daily_bar rows.")
    parser.add_argument("--stocks", help="CSV file containing stock master rows.")
    parser.add_argument("--market-sqlite", help="SQLite store containing stocks and daily_bar tables.")
    parser.add_argument("--positions", help="Optional CSV containing current positions.")
    parser.add_argument("--trade-date", help="YYYY-MM-DD. Defaults to latest bar date.")
    parser.add_argument("--account-id", default="paper")
    parser.add_argument(
        "--strategy",
        default="momentum_rank",
        choices=["momentum_rank", "quality_rank", "momentum_rank_trend", "quality_rank_trend"],
    )
    parser.add_argument("--trend-filter", action="store_true")
    parser.add_argument("--total-asset", type=float, default=1_000_000)
    parser.add_argument("--output", default="research_store/reports/paper_plan.json")
    parser.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    parser.add_argument("--research-report", default="")
    parser.add_argument("--strategy-status", default="paper", choices=["research", "candidate", "paper", "production", "deprecated"])
    parser.add_argument(
        "--allow-missing-research-report",
        action="store_true",
        help="Development-only bypass for paper trading admission.",
    )
    parser.add_argument(
        "--apply-fills",
        action="store_true",
        help="Simulate fills for accepted order intents and update paper account state.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.market_sqlite:
        market_store = SqliteStore(Path(args.market_sqlite))
        bars = market_store.load_daily_bars(adj_type="qfq")
        if bars.empty:
            bars = market_store.load_daily_bars()
        stocks = market_store.load_stocks()
    else:
        if not args.bars or not args.stocks:
            raise ValueError("either --market-sqlite or both --bars and --stocks are required")
        bars = CsvDailyBarRepository(Path(args.bars)).load()
        stocks = CsvStockRepository(Path(args.stocks)).load()
    store = SqliteStore(Path(args.sqlite))
    store.init_schema()
    current_positions = _load_positions(args.positions)
    trade_date = _resolve_trade_date(args.trade_date, bars)
    previous_snapshot = store.load_latest_portfolio_snapshot(args.account_id, before_date=trade_date)
    if current_positions is None and args.apply_fills:
        current_positions = store.load_latest_positions(args.account_id, before_date=trade_date)
        if current_positions.empty:
            current_positions = None
    effective_total_asset = previous_snapshot.total_asset if previous_snapshot is not None else args.total_asset

    engine = PaperTradingEngine(
        admission_policy=StrategyAdmissionPolicy(
            require_research_report=not args.allow_missing_research_report,
            require_existing_report=not args.allow_missing_research_report,
        )
    )
    plan = engine.build_plan(
        trade_date=trade_date,
        bars=bars,
        stocks=stocks,
        strategy=build_strategy(args.strategy, trend_filter=args.trend_filter),
        account_id=args.account_id,
        total_asset=effective_total_asset,
        current_positions=current_positions,
        research_report_path=args.research_report,
        strategy_status=args.strategy_status,
    )

    fill_state = None
    if args.apply_fills:
        latest_bars = bars[bars["trade_date"] == trade_date]
        fill_state = PaperExecutionSimulator().apply_orders(
            account_id=args.account_id,
            trade_date=trade_date,
            orders=plan.order_intents,
            latest_bars=latest_bars,
            previous_positions=current_positions,
            previous_snapshot=previous_snapshot,
            initial_cash=args.total_asset,
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "trade_date": plan.trade_date.isoformat(),
                "risk_reasons": list(plan.risk_reasons),
                "admission_reasons": list(plan.admission_reasons),
                "strategy": {
                    "strategy_id": plan.strategy_registration.strategy_id,
                    "strategy_version": plan.strategy_registration.strategy_version,
                    "status": plan.strategy_registration.status,
                    "factor_set_id": plan.strategy_registration.factor_set_id,
                    "research_report_path": plan.strategy_registration.research_report_path,
                    "code_hash": plan.strategy_registration.code_hash,
                    "config_hash": plan.strategy_registration.config_hash,
                    "config_json": plan.strategy_registration.config_json,
                },
                "target_weights": plan.target_weights.to_dict(orient="records"),
                "order_intents": [intent.to_dict() for intent in plan.order_intents],
                "rejected_order_intents": [
                    rejected.to_dict() for rejected in plan.rejected_order_intents
                ],
                "fills": [fill.to_dict() for fill in fill_state.fills] if fill_state else [],
                "fill_rejected_orders": [
                    order.to_dict() for order in fill_state.rejected_orders
                ] if fill_state else [],
                "portfolio_snapshot": fill_state.snapshot.to_dict() if fill_state else None,
                "positions": _records(fill_state.positions) if fill_state else [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    store.save_strategy(plan.strategy_registration)
    store.save_universe_snapshot("a_share_v1", plan.trade_date, plan.universe_snapshot)
    store.save_signals(plan.signals)
    store.save_order_intents(plan.order_intents)
    store.save_order_risk_results(
        [
            *[
                OrderRiskResult(order=intent, decision=RiskDecision.allow())
                for intent in plan.order_intents
            ],
            *plan.rejected_order_intents,
        ]
    )
    if fill_state is not None:
        store.save_order_fills(fill_state.fills)
        store.save_positions(fill_state.positions)
        store.save_portfolio_snapshots([fill_state.snapshot])
    print(f"Wrote paper trading plan to {output}")
    print(f"Saved audit trail to {args.sqlite}")


def _load_positions(path: str | None) -> pd.DataFrame | None:
    if not path:
        return None
    df = pd.read_csv(path)
    if "ts_code" not in df.columns or ("quantity" not in df.columns and "available_quantity" not in df.columns):
        raise ValueError("positions CSV must contain ts_code and quantity or available_quantity")
    return df


def _resolve_trade_date(value: str | None, bars: pd.DataFrame):
    if value:
        return pd.to_datetime(value).date()
    return max(bars["trade_date"])


def _records(df: pd.DataFrame) -> list[dict[str, object]]:
    records = df.to_dict(orient="records")
    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "isoformat"):
                record[key] = value.isoformat()
    return records


if __name__ == "__main__":
    main()
