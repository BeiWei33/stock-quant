from __future__ import annotations

import pandas as pd

from quant.core.models import RiskDecision


class RiskEngine:
    def __init__(self, max_single_weight: float = 0.10, max_total_weight: float = 0.95) -> None:
        self.max_single_weight = max_single_weight
        self.max_total_weight = max_total_weight

    def check_target_weights(self, target_weights: pd.DataFrame) -> RiskDecision:
        if target_weights.empty:
            return RiskDecision.allow()

        reasons: list[str] = []
        if (target_weights["target_weight"] > self.max_single_weight + 1e-12).any():
            reasons.append("single stock weight exceeds limit")
        if target_weights["target_weight"].sum() > self.max_total_weight + 1e-12:
            reasons.append("total position ratio exceeds limit")

        return RiskDecision.reject(*reasons) if reasons else RiskDecision.allow()
