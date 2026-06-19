from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class TradeReconciliationReport:
    account_id: str
    trade_date: date
    status: str
    order_differences: pd.DataFrame
    fill_differences: pd.DataFrame
    local_order_count: int
    broker_order_count: int
    local_fill_count: int
    broker_fill_count: int

    @property
    def report_id(self) -> str:
        return f"{self.account_id}:{self.trade_date.isoformat()}:trades"

    @property
    def local_count(self) -> int:
        return self.local_order_count + self.local_fill_count

    @property
    def broker_count(self) -> int:
        return self.broker_order_count + self.broker_fill_count

    @property
    def differences(self) -> pd.DataFrame:
        frames = []
        if not self.order_differences.empty:
            frames.append(self.order_differences.assign(section="orders"))
        if not self.fill_differences.empty:
            frames.append(self.fill_differences.assign(section="fills"))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "account_id": self.account_id,
            "trade_date": self.trade_date.isoformat(),
            "status": self.status,
            "local_order_count": self.local_order_count,
            "broker_order_count": self.broker_order_count,
            "local_fill_count": self.local_fill_count,
            "broker_fill_count": self.broker_fill_count,
            "order_differences": self.order_differences.to_dict(orient="records"),
            "fill_differences": self.fill_differences.to_dict(orient="records"),
        }


def reconcile_trade_activity(
    *,
    account_id: str,
    trade_date: date,
    local_orders: pd.DataFrame | None = None,
    broker_orders: pd.DataFrame | None = None,
    local_fills: pd.DataFrame | None = None,
    broker_fills: pd.DataFrame | None = None,
    amount_tolerance: float = 0.01,
) -> TradeReconciliationReport:
    local_orders = _empty_frame_if_none(local_orders)
    broker_orders = _empty_frame_if_none(broker_orders)
    local_fills = _empty_frame_if_none(local_fills)
    broker_fills = _empty_frame_if_none(broker_fills)

    order_differences = _compare_order_quantities(local_orders, broker_orders)
    fill_differences = _compare_fills(local_fills, broker_fills, amount_tolerance)
    status = "OK" if order_differences.empty and fill_differences.empty else "DIFF"
    return TradeReconciliationReport(
        account_id=account_id,
        trade_date=trade_date,
        status=status,
        order_differences=order_differences,
        fill_differences=fill_differences,
        local_order_count=len(local_orders),
        broker_order_count=len(broker_orders),
        local_fill_count=len(local_fills),
        broker_fill_count=len(broker_fills),
    )


def _compare_order_quantities(local_orders: pd.DataFrame, broker_orders: pd.DataFrame) -> pd.DataFrame:
    local = _normalize_activity(local_orders, "local_order_quantity", include_amount=False)
    broker = _normalize_activity(broker_orders, "broker_order_quantity", include_amount=False)
    merged = local.merge(broker, on=["ts_code", "side"], how="outer").fillna(0)
    if merged.empty:
        return pd.DataFrame(columns=["ts_code", "side", "local_order_quantity", "broker_order_quantity", "quantity_diff"])
    merged["quantity_diff"] = merged["local_order_quantity"] - merged["broker_order_quantity"]
    return (
        merged[merged["quantity_diff"] != 0]
        .sort_values(["ts_code", "side"])
        .reset_index(drop=True)
    )


def _compare_fills(local_fills: pd.DataFrame, broker_fills: pd.DataFrame, amount_tolerance: float) -> pd.DataFrame:
    local = _normalize_activity(local_fills, "local_fill_quantity", amount_name="local_amount", include_amount=True)
    broker = _normalize_activity(broker_fills, "broker_fill_quantity", amount_name="broker_amount", include_amount=True)
    merged = local.merge(broker, on=["ts_code", "side"], how="outer").fillna(0)
    if merged.empty:
        return pd.DataFrame(
            columns=[
                "ts_code",
                "side",
                "local_fill_quantity",
                "broker_fill_quantity",
                "quantity_diff",
                "local_amount",
                "broker_amount",
                "amount_diff",
            ]
        )
    merged["quantity_diff"] = merged["local_fill_quantity"] - merged["broker_fill_quantity"]
    merged["amount_diff"] = merged["local_amount"] - merged["broker_amount"]
    different = (merged["quantity_diff"] != 0) | (merged["amount_diff"].abs() > amount_tolerance)
    return merged[different].sort_values(["ts_code", "side"]).reset_index(drop=True)


def _normalize_activity(
    activity: pd.DataFrame,
    quantity_name: str,
    *,
    include_amount: bool,
    amount_name: str = "amount",
) -> pd.DataFrame:
    if activity.empty:
        columns = ["ts_code", "side", quantity_name]
        if include_amount:
            columns.append(amount_name)
        return pd.DataFrame(columns=columns)
    required = {"ts_code", "side", "quantity"}
    if not required.issubset(activity.columns):
        raise ValueError("trade activity must contain ts_code, side, and quantity")
    df = activity.copy()
    df["ts_code"] = df["ts_code"].astype(str)
    df["side"] = df["side"].astype(str).str.upper()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    if include_amount:
        if "amount" not in df.columns:
            if "price" not in df.columns:
                df["amount"] = 0.0
            else:
                df["amount"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0) * df["quantity"]
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).astype(float)
        return (
            df.groupby(["ts_code", "side"], as_index=False)
            .agg(quantity=("quantity", "sum"), amount=("amount", "sum"))
            .rename(columns={"quantity": quantity_name, "amount": amount_name})
        )
    return (
        df.groupby(["ts_code", "side"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": quantity_name})
    )


def _empty_frame_if_none(value: pd.DataFrame | None) -> pd.DataFrame:
    return value if value is not None else pd.DataFrame()
