from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PortfolioConfig:
    max_single_weight: float = 0.10
    max_industry_weight: float = 0.30
    cash_reserve: float = 0.10


class PortfolioEngine:
    def __init__(self, config: PortfolioConfig | None = None) -> None:
        self.config = config or PortfolioConfig()

    def build_target_weights(self, signals: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
        if signals.empty:
            return pd.DataFrame(columns=["ts_code", "target_weight"])

        # 直接使用所有信号，不再限制数量（由策略控制）
        selected = signals.copy()
        budget = max(0.0, 1.0 - self.config.cash_reserve)
        n_buy = len(selected[selected["signal_type"] == "BUY"])
        if n_buy == 0:
            n_buy = len(selected)
        equal_weight = min(self.config.max_single_weight, budget / n_buy)
        selected["target_weight"] = selected["signal_type"].apply(
            lambda t: 0.0 if t == "SELL" else equal_weight
        )

        industry_map = universe.set_index("ts_code")["industry"].to_dict()
        selected["industry"] = selected["ts_code"].map(industry_map).fillna("UNKNOWN")
        selected = self._cap_industry(selected)
        return selected[["ts_code", "target_weight"]].reset_index(drop=True)

    def _cap_industry(self, target: pd.DataFrame) -> pd.DataFrame:
        capped = target.copy()
        for industry, group in capped.groupby("industry"):
            weight_sum = group["target_weight"].sum()
            if weight_sum > self.config.max_industry_weight:
                scale = self.config.max_industry_weight / weight_sum
                capped.loc[group.index, "target_weight"] *= scale
        return capped
