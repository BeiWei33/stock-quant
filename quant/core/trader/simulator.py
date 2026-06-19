from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant.core.models import OrderFill, OrderIntent, PortfolioSnapshot


@dataclass(frozen=True)
class FillModelConfig:
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.0005


@dataclass(frozen=True)
class PaperAccountState:
    fills: list[OrderFill]
    positions: pd.DataFrame
    snapshot: PortfolioSnapshot
    rejected_orders: list[OrderIntent]


class PaperExecutionSimulator:
    def __init__(self, config: FillModelConfig | None = None) -> None:
        self.config = config or FillModelConfig()

    def apply_orders(
        self,
        *,
        account_id: str,
        trade_date: date,
        orders: list[OrderIntent],
        latest_bars: pd.DataFrame,
        previous_positions: pd.DataFrame | None,
        previous_snapshot: PortfolioSnapshot | None,
        initial_cash: float,
    ) -> PaperAccountState:
        positions = self._position_book(previous_positions)
        price_col = "open" if "open" in latest_bars.columns else "close"
        price_map = latest_bars.set_index("ts_code")[price_col].astype(float).to_dict()
        cash = previous_snapshot.cash if previous_snapshot is not None else initial_cash
        previous_total_asset = previous_snapshot.total_asset if previous_snapshot is not None else initial_cash

        fills: list[OrderFill] = []
        rejected: list[OrderIntent] = []
        for order in sorted(orders, key=lambda item: 0 if item.side.upper() == "SELL" else 1):
            price = float(price_map.get(order.ts_code, order.price))
            amount = price * order.quantity
            fee = self._commission(amount)
            tax = self._tax(order.side, amount)
            if order.side.upper() == "BUY":
                total_cost = amount + fee + tax
                if cash + 1e-9 < total_cost:
                    rejected.append(order)
                    continue
                cash -= total_cost
                self._buy(positions, order.ts_code, order.quantity, total_cost)
            else:
                current_qty = int(positions.get(order.ts_code, {}).get("quantity", 0))
                sell_qty = min(order.quantity, current_qty)
                if sell_qty <= 0:
                    rejected.append(order)
                    continue
                amount = price * sell_qty
                fee = self._commission(amount)
                tax = self._tax(order.side, amount)
                cash += amount - fee - tax
                self._sell(positions, order.ts_code, sell_qty)

            fills.append(
                OrderFill(
                    fill_id=f"{order.order_id}:FILL",
                    order_id=order.order_id,
                    account_id=order.account_id,
                    strategy_id=order.strategy_id,
                    ts_code=order.ts_code,
                    side=order.side,
                    price=price,
                    quantity=order.quantity if order.side.upper() == "BUY" else min(order.quantity, current_qty),
                    amount=amount,
                    fee=fee,
                    tax=tax,
                    trade_date=trade_date,
                )
            )

        positions_df = self._positions_frame(account_id, trade_date, positions, price_map)
        market_value = float(positions_df["market_value"].sum()) if not positions_df.empty else 0.0
        total_asset = cash + market_value
        daily_return = total_asset / previous_total_asset - 1.0 if previous_total_asset > 0 else 0.0
        previous_peak = previous_total_asset if previous_snapshot is None else max(
            previous_snapshot.total_asset / (1.0 + previous_snapshot.drawdown)
            if previous_snapshot.drawdown > -1.0
            else previous_snapshot.total_asset,
            previous_snapshot.total_asset,
        )
        high_watermark = max(previous_peak, total_asset)
        drawdown = total_asset / high_watermark - 1.0 if high_watermark > 0 else 0.0
        initial_asset = previous_total_asset / (1.0 + previous_snapshot.cum_return) if previous_snapshot else initial_cash
        cum_return = total_asset / initial_asset - 1.0 if initial_asset > 0 else 0.0
        snapshot = PortfolioSnapshot(
            account_id=account_id,
            trade_date=trade_date,
            total_asset=total_asset,
            cash=cash,
            market_value=market_value,
            total_position_ratio=market_value / total_asset if total_asset > 0 else 0.0,
            daily_return=daily_return,
            cum_return=cum_return,
            drawdown=drawdown,
        )
        return PaperAccountState(
            fills=fills,
            positions=positions_df,
            snapshot=snapshot,
            rejected_orders=rejected,
        )

    def _commission(self, amount: float) -> float:
        return max(self.config.min_commission, amount * self.config.commission_rate) if amount > 0 else 0.0

    def _tax(self, side: str, amount: float) -> float:
        return amount * self.config.stamp_tax_rate if side.upper() == "SELL" else 0.0

    def _position_book(self, positions: pd.DataFrame | None) -> dict[str, dict[str, float]]:
        if positions is None or positions.empty:
            return {}
        book: dict[str, dict[str, float]] = {}
        for row in positions.itertuples(index=False):
            quantity = int(row.quantity)
            if quantity <= 0:
                continue
            book[str(row.ts_code)] = {
                "quantity": quantity,
                "avg_cost": float(getattr(row, "avg_cost", 0.0) or 0.0),
            }
        return book

    def _buy(self, positions: dict[str, dict[str, float]], ts_code: str, quantity: int, total_cost: float) -> None:
        current = positions.setdefault(ts_code, {"quantity": 0, "avg_cost": 0.0})
        old_qty = int(current["quantity"])
        old_cost = float(current["avg_cost"]) * old_qty
        new_qty = old_qty + quantity
        current["quantity"] = new_qty
        current["avg_cost"] = (old_cost + total_cost) / new_qty if new_qty > 0 else 0.0

    def _sell(self, positions: dict[str, dict[str, float]], ts_code: str, quantity: int) -> None:
        current = positions.get(ts_code)
        if current is None:
            return
        current["quantity"] = max(0, int(current["quantity"]) - quantity)
        if current["quantity"] <= 0:
            positions.pop(ts_code, None)

    def _positions_frame(
        self,
        account_id: str,
        trade_date: date,
        positions: dict[str, dict[str, float]],
        price_map: dict[str, float],
    ) -> pd.DataFrame:
        rows = []
        for ts_code, item in sorted(positions.items()):
            quantity = int(item["quantity"])
            close = float(price_map.get(ts_code, item["avg_cost"]))
            market_value = quantity * close
            rows.append(
                {
                    "account_id": account_id,
                    "ts_code": ts_code,
                    "trade_date": trade_date,
                    "quantity": quantity,
                    "available_quantity": quantity,
                    "avg_cost": float(item["avg_cost"]),
                    "market_value": market_value,
                    "weight": 0.0,
                }
            )
        frame = pd.DataFrame(rows)
        if not frame.empty:
            total = float(frame["market_value"].sum())
            frame["weight"] = frame["market_value"] / total if total > 0 else 0.0
        return frame
