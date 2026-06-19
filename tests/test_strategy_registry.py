from __future__ import annotations

from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.strategy.registry import build_strategy_registration
from quant.core.strategy.trend import TrendFilterStrategy


def test_strategy_registration_hash_is_stable_for_same_config() -> None:
    first = build_strategy_registration(
        MomentumRankStrategy(top_pct=0.2, max_holdings=5),
        description="test",
        factor_set_id="momentum_60d",
    )
    second = build_strategy_registration(
        MomentumRankStrategy(top_pct=0.2, max_holdings=5),
        description="test",
        factor_set_id="momentum_60d",
    )

    assert first.code_hash == second.code_hash
    assert first.config_hash == second.config_hash
    assert '"top_pct":0.2' in first.config_json


def test_strategy_registration_hash_changes_when_parameters_change() -> None:
    conservative = build_strategy_registration(
        MomentumRankStrategy(top_pct=0.1, max_holdings=5),
        description="test",
        factor_set_id="momentum_60d",
    )
    wider = build_strategy_registration(
        MomentumRankStrategy(top_pct=0.3, max_holdings=5),
        description="test",
        factor_set_id="momentum_60d",
    )

    assert conservative.code_hash == wider.code_hash
    assert conservative.config_hash != wider.config_hash


def test_trend_filter_manifest_includes_base_strategy() -> None:
    registration = build_strategy_registration(
        TrendFilterStrategy(MomentumRankStrategy(top_pct=0.2, max_holdings=5), ma_window=60),
        description="test",
        factor_set_id="momentum_60d",
    )

    assert "TrendFilterStrategy" in registration.config_json
    assert "MomentumRankStrategy" in registration.config_json
    assert '"ma_window":60' in registration.config_json
