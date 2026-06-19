from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.models import OrderIntent, PortfolioSnapshot
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.trader.simulator import FillModelConfig, PaperExecutionSimulator


def _buy_order(ts_code: str = "000001.SZ", quantity: int = 100, price: float = 10.0) -> OrderIntent:
    return OrderIntent(
        account_id="paper",
        strategy_id="momentum_rank",
        trade_date=date(2024, 1, 2),
        ts_code=ts_code,
        side="BUY",
        quantity=quantity,
        price=price,
        target_weight=0.1,
    )


def test_simulator_applies_buy_fill_and_snapshot() -> None:
    simulator = PaperExecutionSimulator(FillModelConfig(commission_rate=0.0, min_commission=0.0, stamp_tax_rate=0.0))
    state = simulator.apply_orders(
        account_id="paper",
        trade_date=date(2024, 1, 2),
        orders=[_buy_order(quantity=100, price=10.0)],
        latest_bars=pd.DataFrame([{"ts_code": "000001.SZ", "close": 10.0}]),
        previous_positions=None,
        previous_snapshot=None,
        initial_cash=100_000,
    )

    assert len(state.fills) == 1
    assert state.snapshot.cash == 99_000
    assert state.snapshot.market_value == 1_000
    assert state.positions.iloc[0]["quantity"] == 100


def test_simulator_continues_from_previous_positions_and_snapshot() -> None:
    simulator = PaperExecutionSimulator(FillModelConfig(commission_rate=0.0, min_commission=0.0, stamp_tax_rate=0.0))
    previous_positions = pd.DataFrame(
        [
            {
                "account_id": "paper",
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 2),
                "quantity": 100,
                "available_quantity": 100,
                "avg_cost": 10.0,
                "market_value": 1_000.0,
                "weight": 0.01,
            }
        ]
    )
    previous_snapshot = PortfolioSnapshot(
        account_id="paper",
        trade_date=date(2024, 1, 2),
        total_asset=100_000,
        cash=99_000,
        market_value=1_000,
        total_position_ratio=0.01,
        daily_return=0.0,
        cum_return=0.0,
        drawdown=0.0,
    )
    sell = OrderIntent(
        account_id="paper",
        strategy_id="momentum_rank",
        trade_date=date(2024, 1, 3),
        ts_code="000001.SZ",
        side="SELL",
        quantity=100,
        price=11.0,
        target_weight=0.0,
    )

    state = simulator.apply_orders(
        account_id="paper",
        trade_date=date(2024, 1, 3),
        orders=[sell],
        latest_bars=pd.DataFrame([{"ts_code": "000001.SZ", "close": 11.0}]),
        previous_positions=previous_positions,
        previous_snapshot=previous_snapshot,
        initial_cash=100_000,
    )

    assert len(state.fills) == 1
    assert state.positions.empty
    assert state.snapshot.cash == 100_100
    assert state.snapshot.total_asset == 100_100


def test_store_persists_fills_positions_and_snapshot(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    simulator = PaperExecutionSimulator(FillModelConfig(commission_rate=0.0, min_commission=0.0, stamp_tax_rate=0.0))
    state = simulator.apply_orders(
        account_id="paper",
        trade_date=date(2024, 1, 2),
        orders=[_buy_order()],
        latest_bars=pd.DataFrame([{"ts_code": "000001.SZ", "close": 10.0}]),
        previous_positions=None,
        previous_snapshot=None,
        initial_cash=100_000,
    )

    store.save_order_fills(state.fills)
    store.save_positions(state.positions)
    store.save_portfolio_snapshots([state.snapshot])

    assert store.count_rows("order_fill") == 1
    assert store.count_rows("positions") == 1
    assert store.count_rows("portfolio_snapshot") == 1
    assert store.load_latest_positions("paper", before_date=date(2024, 1, 3)).iloc[0]["quantity"] == 100
    assert store.load_latest_portfolio_snapshot("paper", before_date=date(2024, 1, 3)) is not None
