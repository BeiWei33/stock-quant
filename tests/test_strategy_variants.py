from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from quant.core.factor.quality import QualityScoreFactor
from quant.core.strategy.base import StrategyContext
from quant.core.strategy.factory import build_strategy
from quant.core.strategy.quality import QualityRankStrategy
from quant.core.strategy.trend import TrendFilterStrategy


def _bars(days: int = 160, downward: bool = False) -> pd.DataFrame:
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(days)]
    dates = [d for d in dates if d.weekday() < 5]
    rows = []
    for code_idx, code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]):
        price = 10.0
        for trade_date in dates:
            drift = -0.002 if downward else 0.001 * (code_idx + 1)
            price *= 1.0 + drift
            rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date,
                    "adj_type": "qfq",
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1_000_000,
                    "amount": 100_000_000 + code_idx * 10_000_000,
                    "quality_flag": "NORMAL",
                    "roe": 0.08 + code_idx * 0.02,
                    "net_profit_growth": 0.10 + code_idx * 0.03,
                    "debt_to_asset": 0.70 - code_idx * 0.10,
                }
            )
    return pd.DataFrame(rows)


def _universe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"],
            "is_active": [True, True, True, True],
            "industry": ["tech", "tech", "finance", "finance"],
        }
    )


def test_quality_score_factor_uses_fundamental_columns() -> None:
    bars = _bars()
    factor_values = QualityScoreFactor().calculate(bars)
    latest = factor_values[factor_values["trade_date"] == max(bars["trade_date"])]

    top = latest.nlargest(1, "quality_score").iloc[0]
    assert top["ts_code"] == "000004.SZ"
    assert 0.0 <= top["quality_score"] <= 1.0


def test_quality_rank_strategy_selects_highest_quality_names() -> None:
    bars = _bars()
    trade_date = max(bars["trade_date"])
    factors = QualityScoreFactor().calculate(bars)

    signals = QualityRankStrategy(top_pct=0.5, max_holdings=2).generate_signal(
        StrategyContext(
            trade_date=trade_date,
            universe=_universe(),
            bars=bars,
            factors=factors,
        )
    )

    assert signals["ts_code"].tolist() == ["000004.SZ", "000003.SZ"]
    assert signals.iloc[0]["strategy_id"] == "quality_rank"


def test_trend_filter_blocks_signals_when_market_proxy_below_average() -> None:
    bars = _bars(days=180, downward=True)
    trade_date = max(bars["trade_date"])
    strategy = TrendFilterStrategy(QualityRankStrategy(top_pct=0.5, max_holdings=2), ma_window=20)

    signals = strategy.generate_signal(
        StrategyContext(
            trade_date=trade_date,
            universe=_universe(),
            bars=bars,
            factors=QualityScoreFactor().calculate(bars),
        )
    )

    assert signals.empty


def test_strategy_factory_builds_trend_wrapped_quality_strategy() -> None:
    strategy = build_strategy("quality_rank", trend_filter=True)

    assert strategy.strategy_id == "quality_rank_trend"
    assert strategy.required_factors()[0].name == "quality_score"
