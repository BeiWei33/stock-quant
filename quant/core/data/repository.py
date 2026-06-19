from __future__ import annotations

from pathlib import Path

import pandas as pd


DAILY_BAR_COLUMNS = {
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
}

STOCK_COLUMNS = {"ts_code", "name", "exchange", "list_date", "is_st", "status"}


class CsvDailyBarRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> pd.DataFrame:
        df = pd.read_csv(self.path)
        missing = DAILY_BAR_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"daily_bar CSV missing columns: {sorted(missing)}")
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        if "quality_flag" not in df.columns:
            df["quality_flag"] = "NORMAL"
        else:
            df["quality_flag"] = df["quality_flag"].fillna("NORMAL")
        if "adj_type" not in df.columns:
            df["adj_type"] = "none"
        else:
            df["adj_type"] = df["adj_type"].fillna("none")
        return df.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)


class CsvStockRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> pd.DataFrame:
        df = pd.read_csv(self.path)
        missing = STOCK_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"stocks CSV missing columns: {sorted(missing)}")
        df = df.copy()
        df["list_date"] = pd.to_datetime(df["list_date"]).dt.date
        if "delist_date" in df.columns:
            df["delist_date"] = pd.to_datetime(df["delist_date"], errors="coerce").dt.date
        else:
            df["delist_date"] = pd.NaT
        df["is_st"] = df["is_st"].map(_parse_bool).fillna(False)
        return df.sort_values("ts_code").reset_index(drop=True)


def close_price_matrix(bars: pd.DataFrame) -> pd.DataFrame:
    return bars.pivot(index="trade_date", columns="ts_code", values="close").sort_index()


def amount_matrix(bars: pd.DataFrame) -> pd.DataFrame:
    return bars.pivot(index="trade_date", columns="ts_code", values="amount").sort_index()


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "st"}
