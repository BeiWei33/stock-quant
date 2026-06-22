from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant.core.backtest.engine import BacktestEngine, BacktestRequest, BacktestResult
from quant.core.backtest.metrics import performance_metrics
from quant.core.benchmark.returns import benchmark_returns as build_benchmark_returns
from quant.core.capital_allocation import AllocationConfig, AllocationResult, CapitalAllocationEngine
from quant.core.factor.technical import FactorEngine
from quant.core.strategy.base import Strategy


@dataclass(frozen=True)
class MultiStrategyBacktestRequest:
    bars: pd.DataFrame
    stocks: pd.DataFrame
    strategies: list[Strategy]
    allocation_config: AllocationConfig | None = None
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
class MultiStrategyBacktestResult:
    strategy_results: dict[str, BacktestResult]
    strategy_returns: pd.DataFrame
    allocation_records: list[AllocationResult]
    allocation_history: pd.DataFrame
    portfolio_returns: pd.Series
    benchmark_returns: pd.Series
    active_returns: pd.Series
    equity_curve: pd.Series
    benchmark_equity_curve: pd.Series
    metrics: dict[str, object]


class MultiStrategyBacktestEngine:
    def __init__(
        self,
        backtest_engine: BacktestEngine | None = None,
        allocation_engine: CapitalAllocationEngine | None = None,
    ) -> None:
        self.backtest_engine = backtest_engine
        self.allocation_engine = allocation_engine

    def run(self, request: MultiStrategyBacktestRequest) -> MultiStrategyBacktestResult:
        if not request.strategies:
            raise ValueError("multi-strategy backtest requires at least one strategy")

        strategy_results = self._run_strategies(request)
        strategy_returns = self._strategy_returns_frame(strategy_results)
        allocator = self.allocation_engine or CapitalAllocationEngine(request.allocation_config)
        allocation_records: list[AllocationResult] = []
        allocation_rows: list[dict[str, object]] = []
        portfolio_returns: list[tuple[date, float]] = []

        for idx, trade_date in enumerate(strategy_returns.index):
            if idx == 0:
                allocation = _initial_equal_allocation(
                    strategy_ids=list(strategy_returns.columns),
                    allocation_date=trade_date,
                    config=allocator.config,
                )
            else:
                history = _long_returns(strategy_returns.iloc[:idx])
                allocation = allocator.allocate(history, allocation_date=strategy_returns.index[idx - 1])
            weights = _weights_for_strategies(allocation, strategy_returns.columns)
            daily_return = float(strategy_returns.loc[trade_date].mul(weights, fill_value=0.0).sum())
            allocation_records.append(allocation)
            allocation_rows.append(_allocation_row(trade_date, allocation, weights))
            portfolio_returns.append((trade_date, daily_return))

        portfolio_returns_series = pd.Series(dict(portfolio_returns)).sort_index()
        benchmark_returns = build_benchmark_returns(
            bars=request.bars,
            benchmark_bars=request.benchmark_bars,
            benchmark_code=request.benchmark_code,
        ).reindex(portfolio_returns_series.index).fillna(0.0)
        active_returns = portfolio_returns_series - benchmark_returns
        equity_curve = (1.0 + portfolio_returns_series.fillna(0.0)).cumprod() * request.initial_cash
        benchmark_equity_curve = (1.0 + benchmark_returns.fillna(0.0)).cumprod() * request.initial_cash
        metrics = performance_metrics(portfolio_returns_series, benchmark_returns)
        metrics["strategy_count"] = float(len(strategy_results))
        metrics["allocation_method"] = allocator.config.method
        metrics["average_cash_weight"] = (
            float(pd.DataFrame(allocation_rows)["cash_weight"].mean()) if allocation_rows else 0.0
        )
        return MultiStrategyBacktestResult(
            strategy_results=strategy_results,
            strategy_returns=strategy_returns,
            allocation_records=allocation_records,
            allocation_history=pd.DataFrame(allocation_rows),
            portfolio_returns=portfolio_returns_series,
            benchmark_returns=benchmark_returns,
            active_returns=active_returns,
            equity_curve=equity_curve,
            benchmark_equity_curve=benchmark_equity_curve,
            metrics=metrics,
        )

    def _run_strategies(self, request: MultiStrategyBacktestRequest) -> dict[str, BacktestResult]:
        results: dict[str, BacktestResult] = {}
        for strategy in request.strategies:
            if strategy.strategy_id in results:
                raise ValueError(f"duplicate strategy_id: {strategy.strategy_id}")
            engine = self.backtest_engine or BacktestEngine(
                factor_engine=FactorEngine(strategy.required_factors())
            )
            results[strategy.strategy_id] = engine.run(
                BacktestRequest(
                    bars=request.bars,
                    stocks=request.stocks,
                    strategy=strategy,
                    benchmark_bars=request.benchmark_bars,
                    benchmark_code=request.benchmark_code,
                    initial_cash=request.initial_cash,
                    account_id=request.account_id,
                    rebalance=request.rebalance,
                    commission_rate=request.commission_rate,
                    min_commission=request.min_commission,
                    stamp_tax_rate=request.stamp_tax_rate,
                    slippage_bps=request.slippage_bps,
                )
            )
        return results

    @staticmethod
    def _strategy_returns_frame(strategy_results: dict[str, BacktestResult]) -> pd.DataFrame:
        frame = pd.DataFrame(
            {
                strategy_id: result.returns
                for strategy_id, result in strategy_results.items()
            }
        ).sort_index()
        return frame.fillna(0.0)


def _initial_equal_allocation(
    *,
    strategy_ids: list[str],
    allocation_date: object,
    config: AllocationConfig,
) -> AllocationResult:
    weight = min(1.0 / len(strategy_ids), config.max_strategy_weight)
    rows: list[dict[str, object]] = [
        {
            "strategy_id": strategy_id,
            "capital_weight": weight,
            "is_cash": False,
        }
        for strategy_id in sorted(strategy_ids)
    ]
    allocated_weight = float(weight * len(strategy_ids))
    cash_weight = max(0.0, 1.0 - allocated_weight)
    if cash_weight > 0:
        rows.append(
            {
                "strategy_id": config.cash_strategy_id,
                "capital_weight": cash_weight,
                "is_cash": True,
            }
        )
    weights = pd.DataFrame(rows, columns=["strategy_id", "capital_weight", "is_cash"])
    return AllocationResult(
        allocation_date=allocation_date,
        method=config.method,
        weights=weights,
        diagnostics={
            "strategy_count": len(strategy_ids),
            "cash_weight": cash_weight,
            "allocated_weight": allocated_weight,
            "portfolio_volatility": 0.0,
            "max_strategy_weight": weight,
            "min_strategy_weight": weight,
            "cash_strategy_id": config.cash_strategy_id,
        },
    )


def _long_returns(returns: pd.DataFrame) -> pd.DataFrame:
    records = returns.copy()
    records.index.name = "trade_date"
    return (
        records.reset_index()
        .melt(id_vars="trade_date", var_name="strategy_id", value_name="return")
        .sort_values(["trade_date", "strategy_id"])
        .reset_index(drop=True)
    )


def _weights_for_strategies(allocation: AllocationResult, strategy_ids: pd.Index) -> pd.Series:
    weights = pd.Series(0.0, index=strategy_ids, dtype=float)
    if allocation.weights.empty:
        return weights
    active = allocation.weights[~allocation.weights["is_cash"].astype(bool)]
    for row in active.itertuples(index=False):
        if row.strategy_id in weights.index:
            weights.loc[row.strategy_id] = float(row.capital_weight)
    return weights


def _allocation_row(
    trade_date: object,
    allocation: AllocationResult,
    strategy_weights: pd.Series,
) -> dict[str, object]:
    cash_weight = float(allocation.diagnostics.get("cash_weight", 0.0))
    if not allocation.weights.empty:
        cash_rows = allocation.weights[allocation.weights["is_cash"].astype(bool)]
        if not cash_rows.empty:
            cash_weight = float(cash_rows["capital_weight"].sum())
    return {
        "trade_date": trade_date,
        "allocation_date": allocation.allocation_date,
        "method": allocation.method,
        "allocated_weight": float(strategy_weights.sum()),
        "cash_weight": cash_weight,
        "max_strategy_weight": float(strategy_weights.max()) if not strategy_weights.empty else 0.0,
        "min_strategy_weight": float(strategy_weights.min()) if not strategy_weights.empty else 0.0,
    }
