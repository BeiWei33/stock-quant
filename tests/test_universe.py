from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.universe.a_share import AShareUniverse, AShareUniverseConfig


def test_a_share_universe_excludes_st_new_and_low_liquidity() -> None:
    stocks = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "name": "A",
                "exchange": "SZ",
                "industry": "bank",
                "list_date": date(2020, 1, 1),
                "is_st": False,
                "status": "listed",
            },
            {
                "ts_code": "000002.SZ",
                "name": "B",
                "exchange": "SZ",
                "industry": "property",
                "list_date": date(2024, 12, 1),
                "is_st": False,
                "status": "listed",
            },
            {
                "ts_code": "000003.SZ",
                "name": "C",
                "exchange": "SZ",
                "industry": "retail",
                "list_date": date(2020, 1, 1),
                "is_st": True,
                "status": "listed",
            },
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "ts_code": code,
                "trade_date": date(2025, 1, day),
                "amount": amount,
                "quality_flag": "NORMAL",
            }
            for code, amount in [("000001.SZ", 80_000_000), ("000002.SZ", 80_000_000), ("000003.SZ", 80_000_000)]
            for day in range(1, 21)
        ]
    )

    universe = AShareUniverse(AShareUniverseConfig(min_list_days=120, min_avg_amount_20d=50_000_000))
    snapshot = universe.get_universe(date(2025, 1, 20), stocks, bars)

    assert snapshot.set_index("ts_code").loc["000001.SZ", "is_active"]
    assert snapshot.set_index("ts_code").loc["000002.SZ", "exclude_reason"] == "NEW_STOCK"
    assert snapshot.set_index("ts_code").loc["000003.SZ", "exclude_reason"] == "ST_STOCK"
