from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from quant.core.universe.base import Universe


@dataclass(frozen=True)
class AShareUniverseConfig:
    min_list_days: int = 120
    min_avg_amount_20d: float = 50_000_000
    include_bj: bool = False
    include_star_market: bool = True
    include_chinext: bool = True


class AShareUniverse(Universe):
    universe_id = "a_share_v1"

    def __init__(self, config: AShareUniverseConfig | None = None) -> None:
        self.config = config or AShareUniverseConfig()

    def get_universe(self, trade_date: date, stocks: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
        recent = bars[bars["trade_date"] <= trade_date].copy()
        today = recent[recent["trade_date"] == trade_date][["ts_code", "quality_flag"]]
        avg_amount = (
            recent.sort_values("trade_date")
            .groupby("ts_code")["amount"]
            .tail(20)
            .groupby(recent.sort_values("trade_date").groupby("ts_code").tail(20)["ts_code"])
            .mean()
        )

        snapshot = stocks.merge(today, on="ts_code", how="left")
        snapshot["avg_amount_20d"] = snapshot["ts_code"].map(avg_amount).fillna(0.0)
        snapshot["include_reason"] = ""
        snapshot["exclude_reason"] = ""
        snapshot["is_active"] = True

        reasons: list[tuple[pd.Series, str]] = [
            (snapshot["is_st"].fillna(False), "ST_STOCK"),
            (~snapshot["status"].fillna("").isin(["listed", "active"]), "NOT_LISTED"),
            (snapshot["quality_flag"].fillna("NORMAL").isin(["SUSPENDED", "ZERO_VOLUME"]), "NOT_TRADABLE"),
            (_list_age_days(snapshot["list_date"], trade_date) < self.config.min_list_days, "NEW_STOCK"),
            (snapshot["avg_amount_20d"] < self.config.min_avg_amount_20d, "LOW_LIQUIDITY"),
        ]

        if not self.config.include_bj:
            reasons.append((snapshot["exchange"].fillna("").eq("BJ"), "BJ_EXCLUDED"))

        for mask, reason in reasons:
            snapshot.loc[mask, "is_active"] = False
            snapshot.loc[mask, "exclude_reason"] = snapshot.loc[mask, "exclude_reason"].mask(
                snapshot.loc[mask, "exclude_reason"].eq(""),
                reason,
            )

        snapshot.loc[snapshot["is_active"], "include_reason"] = "PASS_A_SHARE_V1"
        return snapshot[
            [
                "ts_code",
                "name",
                "exchange",
                "industry",
                "is_active",
                "include_reason",
                "exclude_reason",
                "avg_amount_20d",
            ]
        ].reset_index(drop=True)


def _list_age_days(values: pd.Series, trade_date: date) -> pd.Series:
    dates = pd.to_datetime(values, errors="coerce").dt.date
    return dates.map(lambda item: (trade_date - item).days if pd.notna(item) else 10_000)
