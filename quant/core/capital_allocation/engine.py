from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AllocationConfig:
    method: str = "risk_parity"
    lookback_days: int = 60
    target_volatility: float | None = None
    max_strategy_weight: float = 0.60
    min_strategy_weight: float = 0.0
    max_drawdown_scale_start: float = -0.05
    max_drawdown_scale_stop: float = -0.20
    cash_strategy_id: str = "CASH"


@dataclass(frozen=True)
class AllocationResult:
    allocation_date: object
    method: str
    weights: pd.DataFrame
    diagnostics: dict[str, float | int | str]

    def to_dict(self) -> dict[str, object]:
        return {
            "allocation_date": str(self.allocation_date),
            "method": self.method,
            "weights": self.weights.to_dict(orient="records"),
            "diagnostics": self.diagnostics,
        }


class CapitalAllocationEngine:
    def __init__(self, config: AllocationConfig | None = None) -> None:
        self.config = config or AllocationConfig()

    def allocate(self, returns: pd.DataFrame, *, allocation_date: object | None = None) -> AllocationResult:
        self._validate_returns(returns)
        history = returns.copy()
        history["trade_date"] = pd.to_datetime(history["trade_date"]).dt.date
        if allocation_date is None:
            allocation_date = history["trade_date"].max()
        allocation_date = pd.to_datetime(allocation_date).date()
        history = history[history["trade_date"] <= allocation_date].sort_values(["trade_date", "strategy_id"])
        window = history.groupby("strategy_id", group_keys=False).tail(max(1, self.config.lookback_days))
        wide = window.pivot_table(index="trade_date", columns="strategy_id", values="return", aggfunc="mean").fillna(0.0)
        if wide.empty:
            return self._empty_result(allocation_date)

        base_weights = self._base_weights(wide)
        base_weights = self._apply_weight_bounds(base_weights)
        base_weights = self._apply_drawdown_scaling(wide, base_weights)
        base_weights = self._apply_volatility_target(wide, base_weights)
        base_weights = self._normalize_if_over_allocated(base_weights)
        cash_weight = max(0.0, 1.0 - float(base_weights.sum()))

        rows = [
            {
                "strategy_id": strategy_id,
                "capital_weight": float(weight),
                "is_cash": False,
            }
            for strategy_id, weight in base_weights.sort_index().items()
            if weight > 0
        ]
        if cash_weight > 0:
            rows.append(
                {
                    "strategy_id": self.config.cash_strategy_id,
                    "capital_weight": float(cash_weight),
                    "is_cash": True,
                }
            )
        weights = pd.DataFrame(rows, columns=["strategy_id", "capital_weight", "is_cash"])
        diagnostics = self._diagnostics(wide, base_weights, cash_weight)
        return AllocationResult(
            allocation_date=allocation_date,
            method=self.config.method,
            weights=weights,
            diagnostics=diagnostics,
        )

    def _base_weights(self, returns: pd.DataFrame) -> pd.Series:
        strategy_ids = list(returns.columns)
        if not strategy_ids:
            return pd.Series(dtype=float)
        if self.config.method == "equal":
            return pd.Series(1.0 / len(strategy_ids), index=strategy_ids)
        if self.config.method == "risk_parity":
            vol = returns.std(ddof=0).replace(0, np.nan)
            inv_vol = 1.0 / vol
            if inv_vol.dropna().empty:
                return pd.Series(1.0 / len(strategy_ids), index=strategy_ids)
            weights = inv_vol.fillna(0.0)
            total = float(weights.sum())
            if total <= 0:
                return pd.Series(1.0 / len(strategy_ids), index=strategy_ids)
            return weights / total
        raise ValueError(f"unsupported allocation method: {self.config.method}")

    def _apply_drawdown_scaling(self, returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
        scaled = weights.copy()
        for strategy_id in scaled.index:
            drawdown = _max_drawdown(returns[strategy_id])
            scale = _linear_scale(
                drawdown,
                start=self.config.max_drawdown_scale_start,
                stop=self.config.max_drawdown_scale_stop,
            )
            scaled.loc[strategy_id] *= scale
        return scaled

    def _apply_volatility_target(self, returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
        target = self.config.target_volatility
        if target is None or target <= 0 or weights.empty:
            return weights
        current_vol = _portfolio_volatility(returns, weights)
        if current_vol <= 0:
            return weights
        scale = min(1.0, target / current_vol)
        return weights * scale

    def _apply_weight_bounds(self, weights: pd.Series) -> pd.Series:
        if weights.empty:
            return weights
        return weights.clip(lower=self.config.min_strategy_weight, upper=self.config.max_strategy_weight)

    @staticmethod
    def _normalize_if_over_allocated(weights: pd.Series) -> pd.Series:
        total = float(weights.sum())
        if total > 1.0:
            return weights / total
        return weights

    def _diagnostics(self, returns: pd.DataFrame, weights: pd.Series, cash_weight: float) -> dict[str, float | int | str]:
        strategy_count = int((weights > 0).sum())
        return {
            "strategy_count": strategy_count,
            "cash_weight": float(cash_weight),
            "allocated_weight": float(weights.sum()),
            "portfolio_volatility": _portfolio_volatility(returns, weights),
            "max_strategy_weight": float(weights.max()) if not weights.empty else 0.0,
            "min_strategy_weight": float(weights.min()) if not weights.empty else 0.0,
        }

    def _empty_result(self, allocation_date: object) -> AllocationResult:
        return AllocationResult(
            allocation_date=allocation_date,
            method=self.config.method,
            weights=pd.DataFrame(columns=["strategy_id", "capital_weight", "is_cash"]),
            diagnostics={
                "strategy_count": 0,
                "cash_weight": 0.0,
                "allocated_weight": 0.0,
                "portfolio_volatility": 0.0,
                "max_strategy_weight": 0.0,
                "min_strategy_weight": 0.0,
            },
        )

    @staticmethod
    def _validate_returns(returns: pd.DataFrame) -> None:
        required = {"trade_date", "strategy_id", "return"}
        missing = required - set(returns.columns)
        if missing:
            raise ValueError(f"returns missing required columns: {sorted(missing)}")


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _linear_scale(drawdown: float, *, start: float, stop: float) -> float:
    if stop >= start:
        raise ValueError("max_drawdown_scale_stop must be smaller than max_drawdown_scale_start")
    if drawdown >= start:
        return 1.0
    if drawdown <= stop:
        return 0.0
    return float((drawdown - stop) / (start - stop))


def _portfolio_volatility(returns: pd.DataFrame, weights: pd.Series) -> float:
    if returns.empty or weights.empty:
        return 0.0
    aligned = returns.reindex(columns=weights.index).fillna(0.0)
    portfolio_returns = aligned.mul(weights, axis=1).sum(axis=1)
    return float(portfolio_returns.std(ddof=0) * np.sqrt(252))
