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
    fill_count: int
    rejected_count: int
    fill_rate: float
    partial_fill_count: int
    partial_fill_rate: float
    reject_rate: float
    avg_slippage_bp: float
    max_slippage_bp: float
    min_slippage_bp: float
    slippage_std: float
    drift_details: list[dict[str, object]]

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
            f"| 订单数 | {self.fill_count + self.rejected_count} |",
            f"| 成交数 | {self.fill_count} |",
            f"| 拒绝数 | {self.rejected_count} |",
            f"| 成交率 | {self.fill_rate:.2%} |",
            f"| 拒绝率 | {self.reject_rate:.2%} |",
            f"| 部分成交数 | {self.partial_fill_count} |",
            f"| 部分成交率 | {self.partial_fill_rate:.2%} |",
            f"| 平均滑点 | {self.avg_slippage_bp:.1f} bp |",
            f"| 最大滑点 | {self.max_slippage_bp:.1f} bp |",
            f"| 最小滑点 | {self.min_slippage_bp:.1f} bp |",
            f"| 滑点标准差 | {self.slippage_std:.1f} bp |",
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
        return "\n".join(lines)


def build_drift_report(
    *,
    orders: pd.DataFrame,
    fills: pd.DataFrame,
    trade_date: date,
    account_id: str,
) -> DriftReport:
    if orders.empty and fills.empty:
        return DriftReport(
            trade_date=trade_date, account_id=account_id,
            fill_count=0, rejected_count=0, fill_rate=0.0,
            partial_fill_count=0, partial_fill_rate=0.0, reject_rate=0.0,
            avg_slippage_bp=0.0, max_slippage_bp=0.0, min_slippage_bp=0.0,
            slippage_std=0.0, drift_details=[],
        )

    rejected_count = 0 if orders.empty else len(orders[orders["status"].str.upper() != "CREATED"])
    total_order_count = len(orders)
    fill_count = 0 if fills.empty else len(fills)

    if total_order_count == 0:
        return DriftReport(
            trade_date=trade_date, account_id=account_id,
            fill_count=0, rejected_count=0, fill_rate=0.0,
            partial_fill_count=0, partial_fill_rate=0.0, reject_rate=0.0,
            avg_slippage_bp=0.0, max_slippage_bp=0.0, min_slippage_bp=0.0,
            slippage_std=0.0, drift_details=[],
        )

    fill_rate = fill_count / total_order_count
    reject_rate = rejected_count / total_order_count

    drift_details: list[dict[str, object]] = []
    partial_fill_count = 0

    if not fills.empty and not orders.empty:
        merged = fills.merge(
            orders[["ts_code", "side", "price", "quantity"]],
            on=["ts_code", "side"],
            how="left",
            suffixes=("_fill", "_order"),
        )
        merged["expected_price"] = merged.get("price").fillna(0.0)
        merged["fill_price"] = merged.get("price_fill").fillna(0.0)
        merged["slippage_bp"] = (
            (merged["fill_price"] - merged["expected_price"])
            / merged["expected_price"].clip(lower=0.01)
            * 10000
        )
        slippages = merged["slippage_bp"].dropna()
        avg_slippage = float(slippages.mean()) if not slippages.empty else 0.0
        max_slippage = float(slippages.max()) if not slippages.empty else 0.0
        min_slippage = float(slippages.min()) if not slippages.empty else 0.0
        std_slippage = float(slippages.std(ddof=0)) if not slippages.empty else 0.0

        for _, row in merged.iterrows():
            drift_details.append({
                "ts_code": str(row["ts_code"]),
                "side": str(row["side"]),
                "quantity": int(row.get("quantity_fill", row.get("quantity", 0))),
                "expected_price": float(row["expected_price"]),
                "fill_price": float(row["fill_price"]),
                "slippage_bp": float(row["slippage_bp"]),
            })

        uniq = merged.drop_duplicates(subset=["ts_code", "side"])
        partial_fill_count = sum(
            1 for _, row in uniq.iterrows()
            if int(row.get("quantity_fill", 0)) < int(row.get("quantity_order", 0))
        )
    else:
        avg_slippage = max_slippage = min_slippage = std_slippage = 0.0

    unique_expected = len(orders)
    partial_fill_rate = partial_fill_count / unique_expected if unique_expected > 0 else 0.0

    return DriftReport(
        trade_date=trade_date, account_id=account_id,
        fill_count=fill_count, rejected_count=rejected_count,
        fill_rate=fill_rate, partial_fill_count=partial_fill_count,
        partial_fill_rate=partial_fill_rate, reject_rate=reject_rate,
        avg_slippage_bp=avg_slippage, max_slippage_bp=max_slippage,
        min_slippage_bp=min_slippage, slippage_std=std_slippage,
        drift_details=drift_details,
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
