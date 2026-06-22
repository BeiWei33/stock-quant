from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class DriftReport:
    trade_date: date
    account_id: str
    order_count: int
    filled_order_count: int
    fill_count: int
    rejected_count: int
    unfilled_count: int
    fill_rate: float
    partial_fill_count: int
    partial_fill_rate: float
    reject_rate: float
    avg_slippage_bp: float
    buy_avg_slippage_bp: float
    sell_avg_slippage_bp: float
    max_slippage_bp: float
    min_slippage_bp: float
    slippage_std: float
    expected_notional: float
    filled_notional: float
    commission: float
    tax: float
    explicit_cost: float
    explicit_cost_bp: float
    slippage_cost: float
    slippage_cost_bp: float
    total_execution_cost: float
    total_execution_cost_bp: float
    drift_details: list[dict[str, object]]
    unfilled_details: list[dict[str, object]]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["trade_date"] = self.trade_date.isoformat()
        return payload

    def to_markdown(self) -> str:
        lines = [
            f"# 执行偏差报告 - {self.trade_date}",
            "",
            "| 指标 | 数值 |",
            "| --- | --- |",
            f"| 订单数 | {self.order_count} |",
            f"| 成交订单数 | {self.filled_order_count} |",
            f"| 成交笔数 | {self.fill_count} |",
            f"| 拒绝数 | {self.rejected_count} |",
            f"| 未成交数 | {self.unfilled_count} |",
            f"| 成交率 | {self.fill_rate:.2%} |",
            f"| 拒绝率 | {self.reject_rate:.2%} |",
            f"| 部分成交数 | {self.partial_fill_count} |",
            f"| 部分成交率 | {self.partial_fill_rate:.2%} |",
            f"| 平均滑点 | {self.avg_slippage_bp:.1f} bp |",
            f"| 买入平均滑点 | {self.buy_avg_slippage_bp:.1f} bp |",
            f"| 卖出平均滑点 | {self.sell_avg_slippage_bp:.1f} bp |",
            f"| 最大滑点 | {self.max_slippage_bp:.1f} bp |",
            f"| 最小滑点 | {self.min_slippage_bp:.1f} bp |",
            f"| 滑点标准差 | {self.slippage_std:.1f} bp |",
            f"| 预期成交额 | {self.expected_notional:,.2f} |",
            f"| 实际成交额 | {self.filled_notional:,.2f} |",
            f"| 手续费 | {self.commission:,.2f} |",
            f"| 印花税 | {self.tax:,.2f} |",
            f"| 显性成本 | {self.explicit_cost:,.2f} ({self.explicit_cost_bp:.1f} bp) |",
            f"| 滑点成本 | {self.slippage_cost:,.2f} ({self.slippage_cost_bp:.1f} bp) |",
            f"| 总执行成本 | {self.total_execution_cost:,.2f} ({self.total_execution_cost_bp:.1f} bp) |",
            "",
        ]
        if self.drift_details:
            lines.append("## 逐笔偏差明细")
            lines.append("")
            for detail in self.drift_details[:50]:
                lines.append(
                    f"- {detail['ts_code']} {detail['side']} "
                    f"预期 {detail['expected_price']:.2f} -> "
                    f"实际 {detail['fill_price']:.2f} "
                    f"({detail['slippage_bp']:+.1f} bp, {detail['quantity']}股)"
                )
            if len(self.drift_details) > 50:
                lines.append(f"... 还有 {len(self.drift_details) - 50} 笔未显示")
        if self.unfilled_details:
            lines.append("")
            lines.append("## 未成交/未完全成交")
            lines.append("")
            for detail in self.unfilled_details[:50]:
                lines.append(
                    f"- {detail['ts_code']} {detail['side']} "
                    f"目标 {detail['order_quantity']}股，成交 {detail['filled_quantity']}股，"
                    f"缺口 {detail['unfilled_quantity']}股，状态 {detail['status']}"
                )
            if len(self.unfilled_details) > 50:
                lines.append(f"... 还有 {len(self.unfilled_details) - 50} 笔未显示")
        return "\n".join(lines)


def build_drift_report(
    *,
    orders: pd.DataFrame,
    fills: pd.DataFrame,
    trade_date: date,
    account_id: str,
) -> DriftReport:
    zero_report = DriftReport(
        trade_date=trade_date, account_id=account_id,
        order_count=0, filled_order_count=0,
        fill_count=0, rejected_count=0, unfilled_count=0, fill_rate=0.0,
        partial_fill_count=0, partial_fill_rate=0.0, reject_rate=0.0,
        avg_slippage_bp=0.0, buy_avg_slippage_bp=0.0, sell_avg_slippage_bp=0.0,
        max_slippage_bp=0.0, min_slippage_bp=0.0, slippage_std=0.0,
        expected_notional=0.0, filled_notional=0.0,
        commission=0.0, tax=0.0, explicit_cost=0.0, explicit_cost_bp=0.0,
        slippage_cost=0.0, slippage_cost_bp=0.0,
        total_execution_cost=0.0, total_execution_cost_bp=0.0,
        drift_details=[], unfilled_details=[],
    )
    if orders.empty and fills.empty:
        return zero_report

    total_order_count = len(orders)
    rejected_statuses = {"REJECTED", "CANCELLED", "CANCELED", "FAILED", "BLOCKED"}
    rejected_count = 0 if orders.empty else int(orders["status"].str.upper().isin(rejected_statuses).sum())
    fill_count = 0 if fills.empty else len(fills)

    if total_order_count == 0:
        return zero_report

    filled_order_count = 0
    fill_rate = 0.0
    reject_rate = rejected_count / total_order_count

    drift_details: list[dict[str, object]] = []
    unfilled_details: list[dict[str, object]] = []
    partial_fill_count = 0
    unfilled_count = 0
    expected_notional = float((orders["price"].astype(float) * orders["quantity"].astype(float)).sum()) if not orders.empty else 0.0
    filled_notional = float(fills["amount"].astype(float).sum()) if not fills.empty and "amount" in fills.columns else 0.0
    commission = float(fills["fee"].astype(float).sum()) if not fills.empty and "fee" in fills.columns else 0.0
    tax = float(fills["tax"].astype(float).sum()) if not fills.empty and "tax" in fills.columns else 0.0
    explicit_cost = commission + tax

    if not fills.empty and not orders.empty:
        merged = fills.merge(
            orders[["order_id", "ts_code", "side", "price", "quantity", "status"]],
            on=["order_id", "ts_code", "side"],
            how="left",
            suffixes=("_fill", "_order"),
        )
        merged["expected_price"] = merged.get("price_order").fillna(0.0)
        merged["fill_price"] = merged.get("price_fill").fillna(0.0)
        merged["slippage_bp"] = (
            (merged["fill_price"] - merged["expected_price"])
            / merged["expected_price"].clip(lower=0.01)
            * 10000
        )
        slippages = merged["slippage_bp"].dropna()
        avg_slippage = float(slippages.mean()) if not slippages.empty else 0.0
        buy_slippage = merged.loc[merged["side"].str.upper() == "BUY", "slippage_bp"].dropna()
        sell_slippage = merged.loc[merged["side"].str.upper() == "SELL", "slippage_bp"].dropna()
        buy_avg_slippage = float(buy_slippage.mean()) if not buy_slippage.empty else 0.0
        sell_avg_slippage = float(sell_slippage.mean()) if not sell_slippage.empty else 0.0
        max_slippage = float(slippages.max()) if not slippages.empty else 0.0
        min_slippage = float(slippages.min()) if not slippages.empty else 0.0
        std_slippage = float(slippages.std(ddof=0)) if not slippages.empty else 0.0
        slippage_cost_series = (merged["fill_price"] - merged["expected_price"]) * merged["quantity_fill"]
        slippage_cost_series = slippage_cost_series.where(merged["side"].str.upper() == "BUY", -slippage_cost_series)
        slippage_cost = float(slippage_cost_series.sum())

        for _, row in merged.iterrows():
            drift_details.append({
                "ts_code": str(row["ts_code"]),
                "side": str(row["side"]),
                "quantity": int(row.get("quantity_fill", row.get("quantity", 0))),
                "expected_price": float(row["expected_price"]),
                "fill_price": float(row["fill_price"]),
                "slippage_bp": float(row["slippage_bp"]),
                "slippage_cost": float(
                    (row["fill_price"] - row["expected_price"])
                    * row.get("quantity_fill", row.get("quantity", 0))
                    * (1 if str(row["side"]).upper() == "BUY" else -1)
                ),
                "fee": float(row.get("fee", 0.0) or 0.0),
                "tax": float(row.get("tax", 0.0) or 0.0),
            })

        filled_quantity = (
            fills.groupby("order_id")["quantity"].sum().rename("filled_quantity")
            if "order_id" in fills.columns
            else pd.Series(dtype=float)
        )
        order_fill_state = orders.merge(filled_quantity, left_on="order_id", right_index=True, how="left")
        order_fill_state["filled_quantity"] = order_fill_state["filled_quantity"].fillna(0).astype(int)
        order_fill_state["unfilled_quantity"] = order_fill_state["quantity"].astype(int) - order_fill_state["filled_quantity"]
        filled_order_count = int((order_fill_state["filled_quantity"] > 0).sum())
        fill_rate = filled_order_count / total_order_count
        partial_fill_count = int(((order_fill_state["filled_quantity"] > 0) & (order_fill_state["unfilled_quantity"] > 0)).sum())
        unfilled_count = int((order_fill_state["filled_quantity"] == 0).sum())
        for _, row in order_fill_state.iterrows():
            if int(row["unfilled_quantity"]) > 0:
                unfilled_details.append({
                    "order_id": str(row["order_id"]),
                    "ts_code": str(row["ts_code"]),
                    "side": str(row["side"]),
                    "order_quantity": int(row["quantity"]),
                    "filled_quantity": int(row["filled_quantity"]),
                    "unfilled_quantity": int(row["unfilled_quantity"]),
                    "expected_price": float(row["price"]),
                    "status": str(row["status"]),
                })
    else:
        avg_slippage = buy_avg_slippage = sell_avg_slippage = max_slippage = min_slippage = std_slippage = 0.0
        slippage_cost = 0.0
        if not orders.empty:
            unfilled_count = len(orders)
            unfilled_details = [
                {
                    "order_id": str(row.order_id),
                    "ts_code": str(row.ts_code),
                    "side": str(row.side),
                    "order_quantity": int(row.quantity),
                    "filled_quantity": 0,
                    "unfilled_quantity": int(row.quantity),
                    "expected_price": float(row.price),
                    "status": str(row.status),
                }
                for row in orders.itertuples(index=False)
            ]

    unique_expected = len(orders)
    partial_fill_rate = partial_fill_count / unique_expected if unique_expected > 0 else 0.0
    explicit_cost_bp = explicit_cost / filled_notional * 10000 if filled_notional > 0 else 0.0
    slippage_cost_bp = slippage_cost / filled_notional * 10000 if filled_notional > 0 else 0.0
    total_execution_cost = explicit_cost + slippage_cost
    total_execution_cost_bp = total_execution_cost / filled_notional * 10000 if filled_notional > 0 else 0.0

    return DriftReport(
        trade_date=trade_date, account_id=account_id, order_count=total_order_count,
        filled_order_count=filled_order_count, unfilled_count=unfilled_count,
        fill_count=fill_count, rejected_count=rejected_count,
        fill_rate=fill_rate, partial_fill_count=partial_fill_count,
        partial_fill_rate=partial_fill_rate, reject_rate=reject_rate,
        avg_slippage_bp=avg_slippage, buy_avg_slippage_bp=buy_avg_slippage,
        sell_avg_slippage_bp=sell_avg_slippage, max_slippage_bp=max_slippage,
        min_slippage_bp=min_slippage, slippage_std=std_slippage,
        expected_notional=expected_notional, filled_notional=filled_notional,
        commission=commission, tax=tax, explicit_cost=explicit_cost,
        explicit_cost_bp=explicit_cost_bp, slippage_cost=slippage_cost,
        slippage_cost_bp=slippage_cost_bp, total_execution_cost=total_execution_cost,
        total_execution_cost_bp=total_execution_cost_bp,
        drift_details=drift_details, unfilled_details=unfilled_details,
    )


def write_drift_report(
    report: DriftReport,
    json_path: Path,
    markdown_path: Path,
) -> tuple[Path, Path]:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(report.to_markdown(), encoding="utf-8")
    return json_path, markdown_path
