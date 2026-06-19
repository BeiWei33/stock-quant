from __future__ import annotations

import pandas as pd

from quant.core.data.repository import close_price_matrix


def equal_weight_returns(bars: pd.DataFrame) -> pd.Series:
    close = close_price_matrix(bars)
    returns = close.pct_change().replace([pd.NA, pd.NaT], 0.0).fillna(0.0)
    return returns.mean(axis=1).rename("equal_weight_return")
