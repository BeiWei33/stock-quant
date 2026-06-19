from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.execution.rebalance import RebalancePlanner


def test_rebalance_planner_generates_sell_before_buy_and_round_lots() -> None:
    planner = RebalancePlanner()
    target = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "target_weight": 0.10},
            {"ts_code": "000002.SZ", "target_weight": 0.10},
        ]
    )
    latest = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "close": 10.0},
            {"ts_code": "000002.SZ", "close": 20.0},
            {"ts_code": "000003.SZ", "close": 10.0},
        ]
    )
    current = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "quantity": 5_000},
            {"ts_code": "000003.SZ", "quantity": 1_000},
        ]
    )

    intents = planner.generate_order_intents(
        account_id="paper",
        strategy_id="momentum_rank",
        trade_date=date(2024, 1, 31),
        total_asset=1_000_000,
        target_weights=target,
        latest_bars=latest,
        current_positions=current,
    )

    assert [intent.side for intent in intents] == ["SELL", "BUY", "BUY"]
    assert all(intent.quantity % 100 == 0 for intent in intents)
    assert intents[0].ts_code == "000003.SZ"
