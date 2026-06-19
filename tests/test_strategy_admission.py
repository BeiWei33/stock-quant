from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.strategy.admission import StrategyAdmissionPolicy
from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.trader.paper import PaperTradingEngine


def _fixtures() -> tuple[pd.DataFrame, pd.DataFrame]:
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(160)]
    dates = [d for d in dates if d.weekday() < 5]
    codes = [f"00000{i}.SZ" for i in range(1, 7)]
    bars = []
    for idx, code in enumerate(codes):
        price = 10.0
        for trade_date in dates:
            price *= 1.0 + 0.001 * (idx + 1)
            bars.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date,
                    "adj_type": "qfq",
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1_000_000,
                    "amount": 100_000_000,
                    "quality_flag": "NORMAL",
                }
            )
    stocks = pd.DataFrame(
        {
            "ts_code": codes,
            "name": [f"S{i}" for i in range(len(codes))],
            "exchange": ["SZ"] * len(codes),
            "industry": ["tech"] * len(codes),
            "list_date": [date(2020, 1, 1)] * len(codes),
            "is_st": [False] * len(codes),
            "status": ["listed"] * len(codes),
        }
    )
    return pd.DataFrame(bars), stocks


def test_paper_trading_rejects_missing_research_report() -> None:
    bars, stocks = _fixtures()
    engine = PaperTradingEngine()

    with pytest.raises(ValueError, match="research_report_path is required"):
        engine.build_plan(
            trade_date=max(bars["trade_date"]),
            bars=bars,
            stocks=stocks,
            strategy=MomentumRankStrategy(max_holdings=3, top_pct=0.5),
            account_id="paper",
            total_asset=1_000_000,
        )


def test_paper_trading_accepts_existing_research_report_and_persists_registration(tmp_path) -> None:
    bars, stocks = _fixtures()
    report = tmp_path / "momentum_60d_h5.md"
    report.write_text("# report", encoding="utf-8")
    engine = PaperTradingEngine()

    plan = engine.build_plan(
        trade_date=max(bars["trade_date"]),
        bars=bars,
        stocks=stocks,
        strategy=MomentumRankStrategy(max_holdings=3, top_pct=0.5),
        account_id="paper",
        total_asset=1_000_000,
        research_report_path=str(report),
    )
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    store.save_strategy(plan.strategy_registration)

    saved = store.load_strategy("momentum_rank", "v1")
    assert saved is not None
    assert saved.research_report_path == str(report)
    assert saved.status == "paper"
    assert saved.config_hash
    assert "MomentumRankStrategy" in saved.config_json
    assert plan.rejected_order_intents == []


def test_admission_policy_dev_bypass_allows_missing_report() -> None:
    bars, stocks = _fixtures()
    engine = PaperTradingEngine(
        admission_policy=StrategyAdmissionPolicy(require_research_report=False, require_existing_report=False)
    )

    plan = engine.build_plan(
        trade_date=max(bars["trade_date"]),
        bars=bars,
        stocks=stocks,
        strategy=MomentumRankStrategy(max_holdings=3, top_pct=0.5),
        account_id="paper",
        total_asset=1_000_000,
    )

    assert plan.strategy_registration.research_report_path == ""


def test_paper_trading_places_rejected_orders_in_plan(tmp_path) -> None:
    bars, stocks = _fixtures()
    latest_date = max(bars["trade_date"])
    bars.loc[(bars["trade_date"] == latest_date) & (bars["ts_code"] == "000006.SZ"), "quality_flag"] = "LIMIT_UP"
    report = tmp_path / "momentum_60d_h5.md"
    report.write_text("# report", encoding="utf-8")
    engine = PaperTradingEngine()

    plan = engine.build_plan(
        trade_date=latest_date,
        bars=bars,
        stocks=stocks,
        strategy=MomentumRankStrategy(max_holdings=3, top_pct=0.5),
        account_id="paper",
        total_asset=1_000_000,
        research_report_path=str(report),
    )

    assert any(
        rejected.order.ts_code == "000006.SZ"
        and "limit-up stock cannot be bought" in rejected.decision.reasons
        for rejected in plan.rejected_order_intents
    )
