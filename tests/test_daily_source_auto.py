from __future__ import annotations

from quant.apps.daily import _build_source
from quant.core.collector.fallback_source import FallbackMarketDataSource
from quant.core.config.daily import DailyAppConfig


def test_daily_auto_source_uses_tencent_before_akshare() -> None:
    source = _build_source(DailyAppConfig(source="auto", akshare_limit=2))

    assert isinstance(source, FallbackMarketDataSource)
    assert [item.source_name for item in source.sources] == ["mootdx", "tencent", "baidu", "akshare"]


def test_daily_auto_source_places_tushare_before_akshare_when_token_exists() -> None:
    source = _build_source(
        DailyAppConfig(source="auto", akshare_limit=2, tushare_token="test-token")
    )

    assert isinstance(source, FallbackMarketDataSource)
    assert [item.source_name for item in source.sources] == [
        "mootdx",
        "tencent",
        "baidu",
        "tushare",
        "akshare",
    ]
