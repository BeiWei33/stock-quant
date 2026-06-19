from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from quant.core.models import OrderIntent
from quant.core.risk.china_market.rules import ChinaMarketOrderRisk, ChinaMarketRuleConfig, ChinaMarketRules


def _order(ts_code: str, side: str, quantity: int = 100, price: float = 10.0) -> OrderIntent:
    return OrderIntent(
        account_id="paper",
        strategy_id="test",
        trade_date=date(2024, 1, 31),
        ts_code=ts_code,
        side=side,
        quantity=quantity,
        price=price,
        target_weight=0.1,
    )


def test_china_market_rules_rejects_suspended_limit_and_t1_cases() -> None:
    rules = ChinaMarketRules()

    assert not rules.check_order(_order("000001.SZ", "BUY"), pd.Series({"quality_flag": "SUSPENDED"}), 100_000_000).allowed
    assert not rules.check_order(_order("000001.SZ", "BUY"), pd.Series({"quality_flag": "LIMIT_UP"}), 100_000_000).allowed
    assert not rules.check_order(_order("000001.SZ", "SELL"), pd.Series({"quality_flag": "LIMIT_DOWN"}), 100_000_000).allowed
    decision = rules.check_order(
        _order("000001.SZ", "SELL", quantity=500),
        pd.Series({"quality_flag": "NORMAL"}),
        100_000_000,
        available_quantity=100,
    )
    assert not decision.allowed
    assert "sell quantity exceeds T+1 available quantity" in decision.reasons


def test_china_market_rules_rejects_low_liquidity_and_order_cap() -> None:
    rules = ChinaMarketRules(
        ChinaMarketRuleConfig(min_avg_amount_20d=50_000_000, max_order_amount_ratio=0.01)
    )

    low_liquidity = rules.check_order(
        _order("000001.SZ", "BUY", quantity=100),
        pd.Series({"quality_flag": "NORMAL"}),
        avg_amount_20d=10_000_000,
    )
    large_order = rules.check_order(
        _order("000001.SZ", "BUY", quantity=60_000),
        pd.Series({"quality_flag": "NORMAL"}),
        avg_amount_20d=50_000_000,
    )

    assert not low_liquidity.allowed
    assert "insufficient liquidity for new buy" in low_liquidity.reasons
    assert not large_order.allowed
    assert "order amount exceeds liquidity cap" in large_order.reasons


def test_order_risk_uses_latest_bar_avg_amount_and_available_quantity() -> None:
    start = date(2024, 1, 1)
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": start + timedelta(days=i),
                "amount": 100_000_000,
                "quality_flag": "NORMAL",
            }
            for i in range(20)
        ]
    )
    positions = pd.DataFrame([{"ts_code": "000001.SZ", "quantity": 1_000, "available_quantity": 100}])
    risk = ChinaMarketOrderRisk()

    result = risk.check_orders([_order("000001.SZ", "SELL", quantity=500)], bars, positions)[0]

    assert not result[1].allowed
    assert "sell quantity exceeds T+1 available quantity" in result[1].reasons
