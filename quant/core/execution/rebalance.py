from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant.core.models import OrderIntent


@dataclass(frozen=True)
class RebalanceConfig:
    lot_size: int = 100
    min_trade_amount: float = 1_000


class RebalancePlanner:
    def __init__(self, config: RebalanceConfig | None = None) -> None:
        self.config = config or RebalanceConfig()

    def generate_order_intents(
        self,
        *,
        account_id: str,
        strategy_id: str,
        trade_date: date,
        total_asset: float,
        target_weights: pd.DataFrame,
        latest_bars: pd.DataFrame,
        current_positions: pd.DataFrame | None = None,
    ) -> list[OrderIntent]:
        price_map = latest_bars.set_index("ts_code")["close"].astype(float).to_dict()
        current_quantity = self._current_quantity(current_positions)
        target_weight = target_weights.set_index("ts_code")["target_weight"].astype(float).to_dict()
        all_codes = set(current_quantity) | set(target_weight)

        intents: list[OrderIntent] = []
        for ts_code in sorted(all_codes):
            price = price_map.get(ts_code)
            if price is None or price <= 0:
                continue

            current_qty = current_quantity.get(ts_code, 0)
            desired_value = total_asset * target_weight.get(ts_code, 0.0)
            desired_qty = self._floor_lot(desired_value / price)
            delta = desired_qty - current_qty
            if abs(delta) < self.config.lot_size:
                continue
            if abs(delta) * price < self.config.min_trade_amount:
                continue

            side = "BUY" if delta > 0 else "SELL"
            intents.append(
                OrderIntent(
                    account_id=account_id,
                    strategy_id=strategy_id,
                    trade_date=trade_date,
                    ts_code=ts_code,
                    side=side,
                    quantity=abs(delta),
                    price=price,
                    target_weight=target_weight.get(ts_code, 0.0),
                    reason="rebalance_to_target_weight",
                )
            )

        return sorted(intents, key=lambda intent: 0 if intent.side == "SELL" else 1)

    def _floor_lot(self, quantity: float) -> int:
        return int(quantity // self.config.lot_size) * self.config.lot_size

    def _current_quantity(self, current_positions: pd.DataFrame | None) -> dict[str, int]:
        if current_positions is None or current_positions.empty:
            return {}
        if not {"ts_code", "quantity"}.issubset(current_positions.columns):
            raise ValueError("current_positions must contain ts_code and quantity")
        return {
            str(row.ts_code): int(row.quantity)
            for row in current_positions[["ts_code", "quantity"]].itertuples(index=False)
        }
