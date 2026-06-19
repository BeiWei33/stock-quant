from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    output_dir = Path("research_store/sample")
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2024-01-02", periods=180)
    codes = [f"000{i:03d}.SZ" for i in range(1, 31)]

    stocks = pd.DataFrame(
        {
            "ts_code": codes,
            "name": [f"样例股票{i:03d}" for i in range(1, 31)],
            "exchange": ["SZ"] * len(codes),
            "industry": [f"industry_{i % 5}" for i in range(len(codes))],
            "list_date": ["2020-01-01"] * len(codes),
            "delist_date": [""] * len(codes),
            "is_st": [False] * len(codes),
            "status": ["listed"] * len(codes),
        }
    )

    rows = []
    for code_idx, code in enumerate(codes):
        drift = 0.0002 + code_idx * 0.00002
        returns = rng.normal(drift, 0.018, len(dates))
        close = 10 * np.cumprod(1 + returns)
        for date, price in zip(dates, close):
            rows.append(
                {
                    "ts_code": code,
                    "trade_date": date.date().isoformat(),
                    "adj_type": "qfq",
                    "open": price * rng.uniform(0.99, 1.01),
                    "high": price * rng.uniform(1.00, 1.03),
                    "low": price * rng.uniform(0.97, 1.00),
                    "close": price,
                    "pre_close": price / (1 + rng.normal(drift, 0.018)),
                    "volume": int(rng.integers(2_000_000, 20_000_000)),
                    "amount": float(rng.uniform(60_000_000, 300_000_000)),
                    "source": "sample",
                    "quality_flag": "NORMAL",
                }
            )

    pd.DataFrame(rows).to_csv(output_dir / "daily_bar.csv", index=False)
    stocks.to_csv(output_dir / "stocks.csv", index=False)
    pd.DataFrame(
        [
            {"ts_code": "000002.SZ", "quantity": 8_000},
            {"ts_code": "000008.SZ", "quantity": 5_700},
        ]
    ).to_csv(output_dir / "local_positions.csv", index=False)
    pd.DataFrame(
        [
            {"ts_code": "000002.SZ", "quantity": 8_000},
            {"ts_code": "000008.SZ", "quantity": 5_600},
        ]
    ).to_csv(output_dir / "broker_positions.csv", index=False)
    print(f"Wrote sample data to {output_dir}")


if __name__ == "__main__":
    main()
