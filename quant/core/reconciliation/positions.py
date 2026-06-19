from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class ReconciliationReport:
    account_id: str
    trade_date: date
    status: str
    differences: pd.DataFrame
    local_count: int
    broker_count: int

    @property
    def report_id(self) -> str:
        return f"{self.account_id}:{self.trade_date.isoformat()}:positions"


def reconcile_positions(
    *,
    account_id: str,
    trade_date: date,
    local_positions: pd.DataFrame,
    broker_positions: pd.DataFrame,
) -> ReconciliationReport:
    local = _normalize_positions(local_positions, "local_quantity")
    broker = _normalize_positions(broker_positions, "broker_quantity")
    merged = local.merge(broker, on="ts_code", how="outer").fillna(0)
    merged["quantity_diff"] = merged["local_quantity"] - merged["broker_quantity"]
    differences = merged[merged["quantity_diff"] != 0].sort_values("ts_code").reset_index(drop=True)
    status = "OK" if differences.empty else "DIFF"
    return ReconciliationReport(
        account_id=account_id,
        trade_date=trade_date,
        status=status,
        differences=differences,
        local_count=len(local),
        broker_count=len(broker),
    )


def _normalize_positions(positions: pd.DataFrame, quantity_name: str) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=["ts_code", quantity_name])
    if not {"ts_code", "quantity"}.issubset(positions.columns):
        raise ValueError("positions must contain ts_code and quantity")
    return (
        positions[["ts_code", "quantity"]]
        .groupby("ts_code", as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": quantity_name})
    )
