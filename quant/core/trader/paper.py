from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant.core.execution.rebalance import RebalancePlanner
from quant.core.factor.technical import FactorEngine
from quant.core.models import OrderIntent, OrderRiskResult, StrategyRegistration
from quant.core.portfolio.engine import PortfolioEngine
from quant.core.risk.engine import RiskEngine
from quant.core.risk.china_market.rules import ChinaMarketOrderRisk
from quant.core.strategy.admission import StrategyAdmissionPolicy
from quant.core.strategy.base import Strategy, StrategyContext
from quant.core.strategy.registry import build_strategy_registration
from quant.core.universe.a_share import AShareUniverse


@dataclass(frozen=True)
class PaperTradingPlan:
    trade_date: date
    universe_snapshot: pd.DataFrame
    signals: pd.DataFrame
    target_weights: pd.DataFrame
    order_intents: list[OrderIntent]
    rejected_order_intents: list[OrderRiskResult]
    strategy_registration: StrategyRegistration
    risk_reasons: tuple[str, ...] = ()
    admission_reasons: tuple[str, ...] = ()


class PaperTradingEngine:
    def __init__(
        self,
        universe: AShareUniverse | None = None,
        factor_engine: FactorEngine | None = None,
        portfolio_engine: PortfolioEngine | None = None,
        risk_engine: RiskEngine | None = None,
        rebalance_planner: RebalancePlanner | None = None,
        admission_policy: StrategyAdmissionPolicy | None = None,
        order_risk: ChinaMarketOrderRisk | None = None,
    ) -> None:
        self.universe = universe or AShareUniverse()
        self.factor_engine = factor_engine
        self.portfolio_engine = portfolio_engine or PortfolioEngine()
        self.risk_engine = risk_engine or RiskEngine()
        self.rebalance_planner = rebalance_planner or RebalancePlanner()
        self.admission_policy = admission_policy or StrategyAdmissionPolicy()
        self.order_risk = order_risk or ChinaMarketOrderRisk()

    def build_plan(
        self,
        *,
        trade_date: date,
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        strategy: Strategy,
        account_id: str,
        total_asset: float,
        current_positions: pd.DataFrame | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        research_report_path: str = "",
        strategy_status: str = "paper",
    ) -> PaperTradingPlan:
        history = bars[bars["trade_date"] <= trade_date].sort_values(["trade_date", "ts_code"])
        if history.empty:
            raise ValueError(f"no bars available for {trade_date}")

        registration = build_strategy_registration(
            strategy,
            description=f"{strategy.strategy_id} paper-trading strategy",
            factor_set_id=_factor_set_id(strategy),
            research_report_path=research_report_path,
            status=strategy_status,
        )
        admission = self.admission_policy.check(registration)
        if not admission.allowed:
            raise ValueError("strategy admission rejected: " + "; ".join(admission.reasons))

        factor_engine = self.factor_engine or FactorEngine(strategy.required_factors())
        factors = factor_engine.calculate(history)
        universe_snapshot = self.universe.get_universe(trade_date, stocks, history)
        signals = strategy.generate_signal(
            StrategyContext(
                trade_date=trade_date,
                universe=universe_snapshot,
                bars=history,
                factors=factors,
            )
        )
        # Apply price range filter on signals (BUY signals only, positions stay)
        if price_min is not None or price_max is not None:
            low = price_min if price_min is not None else 0
            high = price_max if price_max is not None else float("inf")
            latest_price = history[history["trade_date"] == trade_date][["ts_code", "close"]]
            if not signals.empty and not latest_price.empty:
                # Only filter BUY signals, keep all existing positions intact
                held_codes = set()
                if current_positions is not None and not current_positions.empty:
                    held_codes = set(current_positions["ts_code"])
                signals = signals.merge(latest_price, on="ts_code", how="inner")
                buy_mask = (signals["signal_type"] == "BUY") & ((signals["close"] < low) | (signals["close"] > high))
                not_buy_or_held = (signals["signal_type"] != "BUY") | (signals["ts_code"].isin(held_codes))
                signals = signals[~buy_mask | not_buy_or_held].drop(columns=["close"]).reset_index(drop=True)
        target_weights = self.portfolio_engine.build_target_weights(signals, universe_snapshot)
        risk_decision = self.risk_engine.check_target_weights(target_weights)
        if not risk_decision.allowed:
            target_weights = pd.DataFrame(columns=["ts_code", "target_weight"])

        latest_bars = history[history["trade_date"] == trade_date]
        candidate_orders = self.rebalance_planner.generate_order_intents(
            account_id=account_id,
            strategy_id=strategy.strategy_id,
            trade_date=trade_date,
            total_asset=total_asset,
            target_weights=target_weights,
            latest_bars=latest_bars,
            current_positions=current_positions,
        )
        order_risk_results = self.order_risk.check_orders(
            candidate_orders,
            history,
            current_positions=current_positions,
        )
        order_intents = [order for order, decision in order_risk_results if decision.allowed]
        rejected_order_intents = [
            OrderRiskResult(order=order, decision=decision)
            for order, decision in order_risk_results
            if not decision.allowed
        ]
        return PaperTradingPlan(
            trade_date=trade_date,
            universe_snapshot=universe_snapshot,
            signals=signals,
            target_weights=target_weights,
            order_intents=order_intents,
            rejected_order_intents=rejected_order_intents,
            strategy_registration=registration,
            risk_reasons=risk_decision.reasons,
            admission_reasons=admission.reasons,
        )


def _factor_set_id(strategy: Strategy) -> str:
    names = [factor.name for factor in strategy.required_factors()]
    return "+".join(names) if names else "none"
