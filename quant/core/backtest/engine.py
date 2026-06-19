from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant.core.backtest.metrics import performance_metrics
from quant.core.benchmark.returns import benchmark_returns as build_benchmark_returns
from quant.core.data.repository import close_price_matrix
from quant.core.execution.rebalance import RebalancePlanner
from quant.core.factor.technical import FactorEngine, MomentumFactor
from quant.core.models import OrderIntent, PortfolioSnapshot, StrategyRegistration
from quant.core.portfolio.engine import PortfolioEngine
from quant.core.risk.engine import RiskEngine
from quant.core.risk.china_market.rules import ChinaMarketOrderRisk
from quant.core.strategy.base import Strategy, StrategyContext
from quant.core.strategy.registry import build_strategy_registration
from quant.core.universe.a_share import AShareUniverse


@dataclass(frozen=True)
class BacktestRequest:
    bars: pd.DataFrame
    stocks: pd.DataFrame
    strategy: Strategy
    benchmark_bars: pd.DataFrame | None = None
    benchmark_code: str = "equal_weight"
    initial_cash: float = 1_000_000
    account_id: str = "paper"
    rebalance: str = "weekly"
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.0005
    slippage_bps: float = 0.0


@dataclass(frozen=True)
class RebalanceRecord:
    trade_date: date
    allowed: bool
    reasons: tuple[str, ...]
    turnover: float
    buy_turnover: float
    sell_turnover: float
    holdings_count: int
    order_count: int
    rejected_order_count: int
    filled_count: int
    rejected_orders: list[dict[str, object]]
    target_weights: list[dict[str, float | str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "turnover": self.turnover,
            "buy_turnover": self.buy_turnover,
            "sell_turnover": self.sell_turnover,
            "holdings_count": self.holdings_count,
            "order_count": self.order_count,
            "rejected_order_count": self.rejected_order_count,
            "filled_count": self.filled_count,
            "rejected_orders": self.rejected_orders,
            "target_weights": self.target_weights,
        }


@dataclass(frozen=True)
class BacktestResult:
    benchmark_code: str
    strategy_registration: StrategyRegistration
    snapshots: list[PortfolioSnapshot]
    rebalance_records: list[RebalanceRecord]
    returns: pd.Series
    benchmark_returns: pd.Series
    active_returns: pd.Series
    equity_curve: pd.Series
    benchmark_equity_curve: pd.Series
    metrics: dict[str, object]


class BacktestEngine:
    def __init__(
        self,
        universe: AShareUniverse | None = None,
        factor_engine: FactorEngine | None = None,
        portfolio_engine: PortfolioEngine | None = None,
        risk_engine: RiskEngine | None = None,
        rebalance_planner: RebalancePlanner | None = None,
        order_risk: ChinaMarketOrderRisk | None = None,
    ) -> None:
        self.universe = universe or AShareUniverse()
        self.factor_engine = factor_engine or FactorEngine([MomentumFactor(60)])
        self.portfolio_engine = portfolio_engine or PortfolioEngine()
        self.risk_engine = risk_engine or RiskEngine()
        self.rebalance_planner = rebalance_planner or RebalancePlanner()
        self.order_risk = order_risk or ChinaMarketOrderRisk()

    def run(self, request: BacktestRequest) -> BacktestResult:
        bars = request.bars.sort_values(["trade_date", "ts_code"]).copy()
        registration = build_strategy_registration(
            request.strategy,
            description=f"{request.strategy.strategy_id} backtest strategy",
            factor_set_id=_factor_set_id(request.strategy),
            status="research",
        )
        factors = self.factor_engine.calculate(bars)
        close = close_price_matrix(bars)
        benchmark_returns = build_benchmark_returns(
            bars=bars,
            benchmark_bars=request.benchmark_bars,
            benchmark_code=request.benchmark_code,
        )
        dates = list(close.index)
        rebalance_dates = set(self._rebalance_dates(dates, request.rebalance))

        quantities = pd.Series(0, index=close.columns, dtype="int64")
        cash = float(request.initial_cash)
        equity = request.initial_cash
        previous_equity = request.initial_cash
        high_watermark = equity
        snapshots: list[PortfolioSnapshot] = []
        rebalance_records: list[RebalanceRecord] = []
        returns: list[tuple[date, float]] = []

        for idx, trade_date in enumerate(dates):
            current_prices = close.iloc[idx].astype(float)
            position_value = quantities.astype(float) * current_prices
            equity_before_trade = cash + float(position_value.sum())
            daily_return = (
                equity_before_trade / previous_equity - 1.0 if previous_equity > 0 else 0.0
            )
            equity = equity_before_trade

            if trade_date in rebalance_dates:
                history = bars[bars["trade_date"] <= trade_date]
                universe_snapshot = self.universe.get_universe(trade_date, request.stocks, history)
                signals = request.strategy.generate_signal(
                    StrategyContext(
                        trade_date=trade_date,
                        universe=universe_snapshot,
                        bars=history,
                        factors=factors[factors["trade_date"] <= trade_date],
                    )
                )
                target = self.portfolio_engine.build_target_weights(signals, universe_snapshot)
                decision = self.risk_engine.check_target_weights(target)
                next_weights = self._target_to_weight_series(target, close.columns)
                current_weights = (
                    position_value / equity if equity > 0 else pd.Series(0.0, index=close.columns)
                )
                turnover_delta = next_weights - current_weights
                current_positions = self._positions_frame(
                    account_id=request.account_id,
                    trade_date=trade_date,
                    quantities=quantities,
                    prices=current_prices,
                    equity=equity,
                )
                orders: list[OrderIntent] = []
                risk_results = []
                filled_orders: list[OrderIntent] = []
                if decision.allowed:
                    latest_bars = history[history["trade_date"] == trade_date]
                    orders = self.rebalance_planner.generate_order_intents(
                        account_id=request.account_id,
                        strategy_id=request.strategy.strategy_id,
                        trade_date=trade_date,
                        total_asset=equity,
                        target_weights=target,
                        latest_bars=latest_bars,
                        current_positions=current_positions,
                    )
                    risk_results = self.order_risk.check_orders(
                        orders,
                        history,
                        current_positions=current_positions,
                    )
                    filled_orders = [order for order, risk_decision in risk_results if risk_decision.allowed]
                    cash, quantities = self._apply_orders(
                        orders=filled_orders,
                        cash=cash,
                        quantities=quantities,
                        close_prices=current_prices,
                        request=request,
                    )
                    equity = cash + float((quantities.astype(float) * current_prices).sum())
                    position_value = quantities.astype(float) * current_prices
                record = RebalanceRecord(
                    trade_date=trade_date,
                    allowed=decision.allowed,
                    reasons=decision.reasons,
                    turnover=float(turnover_delta.abs().sum()),
                    buy_turnover=float(turnover_delta.clip(lower=0.0).sum()),
                    sell_turnover=float((-turnover_delta.clip(upper=0.0)).sum()),
                    holdings_count=int((quantities > 0).sum()) if decision.allowed else 0,
                    order_count=len(orders),
                    rejected_order_count=sum(1 for _, risk_decision in risk_results if not risk_decision.allowed),
                    filled_count=len(filled_orders),
                    rejected_orders=_rejected_order_records(risk_results),
                    target_weights=_target_records(target),
                )
                rebalance_records.append(record)

            daily_return = equity / previous_equity - 1.0 if previous_equity > 0 else 0.0
            high_watermark = max(high_watermark, equity)
            drawdown = equity / high_watermark - 1.0
            market_value = float(position_value.sum())
            cash = equity - market_value
            cum_return = equity / request.initial_cash - 1.0
            snapshots.append(
                PortfolioSnapshot(
                    account_id=request.account_id,
                    trade_date=trade_date,
                    total_asset=equity,
                    cash=cash,
                    market_value=market_value,
                    total_position_ratio=market_value / equity if equity > 0 else 0.0,
                    daily_return=daily_return,
                    cum_return=cum_return,
                    drawdown=drawdown,
                    benchmark_return=float(benchmark_returns.get(trade_date, 0.0)),
                    excess_return=daily_return - float(benchmark_returns.get(trade_date, 0.0)),
                )
            )
            returns.append((trade_date, daily_return))
            previous_equity = equity

        returns_series = pd.Series(dict(returns)).sort_index()
        benchmark_returns = benchmark_returns.reindex(returns_series.index).fillna(0.0)
        active_returns = returns_series - benchmark_returns
        equity_curve = (1.0 + returns_series.fillna(0.0)).cumprod() * request.initial_cash
        benchmark_equity_curve = (
            (1.0 + benchmark_returns.fillna(0.0)).cumprod() * request.initial_cash
        )
        metrics = performance_metrics(returns_series, benchmark_returns)
        metrics["benchmark_code"] = request.benchmark_code
        if rebalance_records:
            metrics["rebalance_count"] = float(len(rebalance_records))
            metrics["rejected_rebalance_count"] = float(
                sum(1 for record in rebalance_records if not record.allowed)
            )
            metrics["rejected_order_count"] = float(
                sum(record.rejected_order_count for record in rebalance_records)
            )
            metrics["filled_order_count"] = float(
                sum(record.filled_count for record in rebalance_records)
            )
            metrics["average_turnover"] = float(
                sum(record.turnover for record in rebalance_records) / len(rebalance_records)
            )
            metrics["max_turnover"] = float(max(record.turnover for record in rebalance_records))
        else:
            metrics["rebalance_count"] = 0.0
            metrics["rejected_rebalance_count"] = 0.0
            metrics["rejected_order_count"] = 0.0
            metrics["filled_order_count"] = 0.0
            metrics["average_turnover"] = 0.0
            metrics["max_turnover"] = 0.0
        return BacktestResult(
            benchmark_code=request.benchmark_code,
            strategy_registration=registration,
            snapshots=snapshots,
            rebalance_records=rebalance_records,
            returns=returns_series,
            benchmark_returns=benchmark_returns,
            active_returns=active_returns,
            equity_curve=equity_curve,
            benchmark_equity_curve=benchmark_equity_curve,
            metrics=metrics,
        )

    def _target_to_weight_series(self, target: pd.DataFrame, columns: pd.Index) -> pd.Series:
        weights = pd.Series(0.0, index=columns)
        for row in target.itertuples(index=False):
            if row.ts_code in weights.index:
                weights.loc[row.ts_code] = float(row.target_weight)
        return weights

    def _positions_frame(
        self,
        *,
        account_id: str,
        trade_date: date,
        quantities: pd.Series,
        prices: pd.Series,
        equity: float,
    ) -> pd.DataFrame:
        rows = []
        for ts_code, quantity in quantities.items():
            quantity = int(quantity)
            if quantity <= 0:
                continue
            price = float(prices.get(ts_code, 0.0))
            market_value = quantity * price
            rows.append(
                {
                    "account_id": account_id,
                    "ts_code": ts_code,
                    "trade_date": trade_date,
                    "quantity": quantity,
                    "available_quantity": quantity,
                    "avg_cost": price,
                    "market_value": market_value,
                    "weight": market_value / equity if equity > 0 else 0.0,
                }
            )
        return pd.DataFrame(rows)

    def _apply_orders(
        self,
        *,
        orders: list[OrderIntent],
        cash: float,
        quantities: pd.Series,
        close_prices: pd.Series,
        request: BacktestRequest,
    ) -> tuple[float, pd.Series]:
        updated = quantities.copy()
        for order in sorted(orders, key=lambda item: 0 if item.side.upper() == "SELL" else 1):
            close = float(close_prices.get(order.ts_code, order.price))
            if close <= 0:
                continue
            side = order.side.upper()
            slippage = close * request.slippage_bps / 10_000
            price = close + slippage if side == "BUY" else close - slippage
            if side == "BUY":
                amount = price * order.quantity
                fee = _commission(amount, request.commission_rate, request.min_commission)
                total_cost = amount + fee
                if cash + 1e-9 < total_cost:
                    continue
                cash -= total_cost
                updated.loc[order.ts_code] = int(updated.get(order.ts_code, 0)) + order.quantity
            else:
                current_quantity = int(updated.get(order.ts_code, 0))
                sell_quantity = min(order.quantity, current_quantity)
                if sell_quantity <= 0:
                    continue
                amount = price * sell_quantity
                fee = _commission(amount, request.commission_rate, request.min_commission)
                tax = amount * request.stamp_tax_rate
                cash += amount - fee - tax
                updated.loc[order.ts_code] = current_quantity - sell_quantity
        return cash, updated

    def _rebalance_dates(self, dates: list[date], mode: str) -> list[date]:
        index = pd.to_datetime(pd.Series(dates))
        if mode == "monthly":
            return list(pd.Series(dates).groupby(index.dt.to_period("M")).tail(1))
        if mode == "weekly":
            return list(pd.Series(dates).groupby(index.dt.to_period("W")).tail(1))
        raise ValueError(f"unsupported rebalance mode: {mode}")


def _target_records(target: pd.DataFrame) -> list[dict[str, float | str]]:
    records: list[dict[str, float | str]] = []
    if target.empty:
        return records
    for row in target.itertuples(index=False):
        records.append({"ts_code": str(row.ts_code), "target_weight": float(row.target_weight)})
    return records


def _rejected_order_records(risk_results) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for order, decision in risk_results:
        if decision.allowed:
            continue
        records.append(
            {
                "ts_code": order.ts_code,
                "side": order.side,
                "quantity": order.quantity,
                "price": order.price,
                "reasons": list(decision.reasons),
            }
        )
    return records


def _commission(amount: float, rate: float, minimum: float) -> float:
    return max(minimum, amount * rate) if amount > 0 else 0.0


def _factor_set_id(strategy: Strategy) -> str:
    names = [factor.name for factor in strategy.required_factors()]
    return "+".join(names) if names else "none"
