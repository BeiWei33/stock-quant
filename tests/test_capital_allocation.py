from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from quant.core.capital_allocation import AllocationConfig, CapitalAllocationEngine


def _returns(strategy_returns: dict[str, list[float]]) -> pd.DataFrame:
    start = date(2024, 1, 1)
    rows = []
    for strategy_id, values in strategy_returns.items():
        for idx, value in enumerate(values):
            rows.append(
                {
                    "trade_date": start + timedelta(days=idx),
                    "strategy_id": strategy_id,
                    "return": value,
                }
            )
    return pd.DataFrame(rows)


def _weight(result, strategy_id: str) -> float:
    row = result.weights[result.weights["strategy_id"] == strategy_id]
    if row.empty:
        return 0.0
    return float(row.iloc[0]["capital_weight"])


def test_equal_allocation_splits_capital_across_strategies() -> None:
    result = CapitalAllocationEngine(AllocationConfig(method="equal")).allocate(
        _returns(
            {
                "momentum": [0.01, 0.02, -0.01],
                "quality": [0.00, 0.01, 0.01],
            }
        )
    )

    assert _weight(result, "momentum") == pytest.approx(0.5)
    assert _weight(result, "quality") == pytest.approx(0.5)
    assert _weight(result, "CASH") == 0.0
    assert result.weights["capital_weight"].sum() == pytest.approx(1.0)


def test_risk_parity_allocates_less_to_higher_volatility_strategy() -> None:
    result = CapitalAllocationEngine(AllocationConfig(method="risk_parity")).allocate(
        _returns(
            {
                "steady": [0.002, 0.001, 0.002, 0.001, 0.002],
                "volatile": [0.06, -0.05, 0.04, -0.03, 0.05],
            }
        )
    )

    assert _weight(result, "steady") > _weight(result, "volatile")
    assert result.weights["capital_weight"].sum() == pytest.approx(1.0)


def test_strategy_cap_routes_unused_capital_to_cash() -> None:
    result = CapitalAllocationEngine(
        AllocationConfig(method="equal", max_strategy_weight=0.40)
    ).allocate(
        _returns(
            {
                "momentum": [0.01, 0.02, 0.01],
                "quality": [0.00, 0.01, 0.01],
            }
        )
    )

    assert _weight(result, "momentum") <= 0.40
    assert _weight(result, "quality") <= 0.40
    assert _weight(result, "CASH") == pytest.approx(0.20)
    assert result.weights["capital_weight"].sum() == pytest.approx(1.0)


def test_drawdown_scaling_reduces_strategy_weight_into_cash() -> None:
    result = CapitalAllocationEngine(
        AllocationConfig(
            method="equal",
            max_drawdown_scale_start=-0.05,
            max_drawdown_scale_stop=-0.20,
        )
    ).allocate(
        _returns(
            {
                "momentum": [0.01, 0.01, 0.01, 0.01],
                "drawdown": [0.00, -0.10, -0.10, 0.00],
            }
        )
    )

    assert _weight(result, "drawdown") < 0.5
    assert _weight(result, "momentum") == pytest.approx(0.5)
    assert _weight(result, "CASH") > 0.0
    assert result.weights["capital_weight"].sum() == pytest.approx(1.0)


def test_volatility_target_scales_down_risky_portfolio_into_cash() -> None:
    result = CapitalAllocationEngine(
        AllocationConfig(method="equal", target_volatility=0.05)
    ).allocate(
        _returns(
            {
                "momentum": [0.05, -0.04, 0.06, -0.05, 0.04],
                "quality": [0.04, -0.03, 0.05, -0.04, 0.03],
            }
        )
    )

    assert _weight(result, "CASH") > 0.0
    assert result.diagnostics["portfolio_volatility"] <= 0.05 + 1e-12
    assert result.weights["capital_weight"].sum() == pytest.approx(1.0)
