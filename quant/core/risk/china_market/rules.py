from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant.core.models import OrderIntent, RiskDecision


@dataclass(frozen=True)
class ChinaMarketRuleConfig:
    lot_size: int = 100
    min_avg_amount_20d: float = 50_000_000
    max_order_amount_ratio: float = 0.01


class ChinaMarketRules:
    def __init__(self, config: ChinaMarketRuleConfig | None = None) -> None:
        self.config = config or ChinaMarketRuleConfig()

    def check_order(
        self,
        order: OrderIntent,
        latest_row: pd.Series,
        avg_amount_20d: float,
        available_quantity: int | None = None,
    ) -> RiskDecision:
        reasons: list[str] = []
        side = order.side.upper()
        quality_flag = str(latest_row.get("quality_flag", "NORMAL"))
        if order.quantity % self.config.lot_size != 0:
            reasons.append("quantity must be round lot")
        if quality_flag == "SUSPENDED":
            reasons.append("suspended stock cannot trade")
        if side == "BUY" and quality_flag == "LIMIT_UP":
            reasons.append("limit-up stock cannot be bought")
        if side == "SELL" and quality_flag == "LIMIT_DOWN":
            reasons.append("limit-down stock cannot be sold")
        if side == "SELL" and available_quantity is not None and order.quantity > available_quantity:
            reasons.append("sell quantity exceeds T+1 available quantity")
        if side == "BUY" and avg_amount_20d < self.config.min_avg_amount_20d:
            reasons.append("insufficient liquidity for new buy")
        if order.price * order.quantity > avg_amount_20d * self.config.max_order_amount_ratio:
            reasons.append("order amount exceeds liquidity cap")

        return RiskDecision.reject(*reasons) if reasons else RiskDecision.allow()


class ChinaMarketOrderRisk:
    def __init__(self, rules: ChinaMarketRules | None = None) -> None:
        self.rules = rules or ChinaMarketRules()

    def check_orders(
        self,
        orders: list[OrderIntent],
        bars: pd.DataFrame,
        current_positions: pd.DataFrame | None = None,
    ) -> list[tuple[OrderIntent, RiskDecision]]:
        latest = self._latest_rows(bars)
        avg_amount = self._avg_amount_20d(bars)
        available = self._available_quantity(current_positions)
        results: list[tuple[OrderIntent, RiskDecision]] = []
        for order in orders:
            latest_row = latest.get(order.ts_code)
            if latest_row is None:
                results.append((order, RiskDecision.reject("missing latest bar for order")))
                continue
            decision = self.rules.check_order(
                order,
                latest_row,
                avg_amount_20d=avg_amount.get(order.ts_code, 0.0),
                available_quantity=available.get(order.ts_code),
            )
            results.append((order, decision))
        return results

    def _latest_rows(self, bars: pd.DataFrame) -> dict[str, pd.Series]:
        if bars.empty:
            return {}
        latest_date = max(bars["trade_date"])
        latest = bars[bars["trade_date"] == latest_date]
        return {str(row.ts_code): row for _, row in latest.iterrows()}

    def _avg_amount_20d(self, bars: pd.DataFrame) -> dict[str, float]:
        if bars.empty:
            return {}
        sorted_bars = bars.sort_values(["ts_code", "trade_date"])
        tail = sorted_bars.groupby("ts_code").tail(20)
        return tail.groupby("ts_code")["amount"].mean().fillna(0.0).astype(float).to_dict()

    def _available_quantity(self, current_positions: pd.DataFrame | None) -> dict[str, int]:
        if current_positions is None or current_positions.empty:
            return {}
        if "available_quantity" in current_positions.columns:
            column = "available_quantity"
        elif "quantity" in current_positions.columns:
            column = "quantity"
        else:
            raise ValueError("current_positions must contain quantity or available_quantity")
        return {
            str(row.ts_code): int(getattr(row, column))
            for row in current_positions[["ts_code", column]].itertuples(index=False)
        }
