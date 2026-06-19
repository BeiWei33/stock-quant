from __future__ import annotations

from quant.apps.strategies import render_strategy_list_markdown, render_strategy_markdown
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.strategy.registry import build_strategy_registration


def test_strategy_markdown_renders_hash_and_manifest() -> None:
    registration = build_strategy_registration(
        MomentumRankStrategy(top_pct=0.2, max_holdings=5),
        description="test",
        factor_set_id="momentum_60d",
        status="paper",
    )

    markdown = render_strategy_markdown(registration)

    assert "momentum_rank" in markdown
    assert registration.config_hash[:12] in markdown
    assert "momentum_60d" in markdown
    assert "MomentumRankStrategy" in markdown


def test_strategy_list_markdown_renders_registered_strategies(tmp_path) -> None:
    registration = build_strategy_registration(
        MomentumRankStrategy(top_pct=0.2, max_holdings=5),
        description="test",
        factor_set_id="momentum_60d",
        status="paper",
    )
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    store.save_strategy(registration)

    markdown = render_strategy_list_markdown(store.list_strategies(status="paper"))

    assert "Strategy Registry" in markdown
    assert "momentum_rank" in markdown
    assert registration.config_hash[:12] in markdown
