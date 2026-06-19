from __future__ import annotations

import pandas as pd

from quant.core.benchmark.equal_weight import equal_weight_returns


def benchmark_returns(
    *,
    bars: pd.DataFrame,
    benchmark_bars: pd.DataFrame | None = None,
    benchmark_code: str = "equal_weight",
) -> pd.Series:
    if benchmark_code == "equal_weight" or benchmark_bars is None:
        return equal_weight_returns(bars).rename(benchmark_code)
    if benchmark_bars.empty:
        raise ValueError(f"benchmark bars are empty for: {benchmark_code}")
    required = {"benchmark_code", "trade_date", "close"}
    missing = required - set(benchmark_bars.columns)
    if missing:
        raise ValueError(f"benchmark_bars missing columns: {sorted(missing)}")
    frame = benchmark_bars[benchmark_bars["benchmark_code"].astype(str) == benchmark_code].copy()
    if frame.empty:
        raise ValueError(f"benchmark code not found: {benchmark_code}")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    close = frame.dropna(subset=["close"]).sort_values("trade_date").set_index("trade_date")["close"]
    returns = close.pct_change().fillna(0.0)
    return returns.rename(benchmark_code)
