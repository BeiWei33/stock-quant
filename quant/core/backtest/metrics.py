from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def performance_metrics(returns: pd.Series, benchmark_returns: pd.Series | None = None) -> dict[str, float]:
    returns = returns.fillna(0.0)
    equity = (1.0 + returns).cumprod()
    periods = max(len(returns), 1)
    annual_return = float(equity.iloc[-1] ** (252 / periods) - 1.0) if periods else 0.0
    volatility = float(returns.std(ddof=0) * np.sqrt(252))
    sharpe = float((returns.mean() * 252) / volatility) if volatility > 0 else 0.0

    metrics = {
        "annual_return": annual_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(equity),
        "total_return": float(equity.iloc[-1] - 1.0) if not equity.empty else 0.0,
    }

    if benchmark_returns is not None:
        strategy_returns, benchmark_returns = returns.align(benchmark_returns.fillna(0.0), join="inner")
        active = strategy_returns - benchmark_returns
        benchmark_equity = (1.0 + benchmark_returns).cumprod()
        tracking_error = float(active.std(ddof=0) * np.sqrt(252))
        benchmark_volatility = float(benchmark_returns.std(ddof=0) * np.sqrt(252))
        benchmark_periods = max(len(benchmark_returns), 1)
        benchmark_total_return = (
            float(benchmark_equity.iloc[-1] - 1.0) if not benchmark_equity.empty else 0.0
        )
        benchmark_annual_return = (
            float(benchmark_equity.iloc[-1] ** (252 / benchmark_periods) - 1.0)
            if not benchmark_equity.empty
            else 0.0
        )
        benchmark_variance = float(benchmark_returns.var(ddof=0))
        covariance = float(strategy_returns.cov(benchmark_returns, ddof=0))
        metrics["benchmark_total_return"] = benchmark_total_return
        metrics["benchmark_annual_return"] = benchmark_annual_return
        metrics["benchmark_volatility"] = benchmark_volatility
        metrics["excess_return"] = float((1.0 + strategy_returns).prod() - (1.0 + benchmark_returns).prod())
        metrics["tracking_error"] = tracking_error
        metrics["information_ratio"] = (
            float(active.mean() * 252 / tracking_error) if tracking_error > 0 else 0.0
        )
        metrics["active_win_rate"] = float((active > 0).mean()) if not active.empty else 0.0
        metrics["benchmark_correlation"] = (
            float(strategy_returns.corr(benchmark_returns))
            if len(strategy_returns) > 1 and strategy_returns.std(ddof=0) > 0 and benchmark_returns.std(ddof=0) > 0
            else 0.0
        )
        metrics["beta"] = float(covariance / benchmark_variance) if benchmark_variance > 0 else 0.0

    return metrics
