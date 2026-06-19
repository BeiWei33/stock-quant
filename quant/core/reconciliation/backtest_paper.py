from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from quant.core.persistence.sqlite_store import SqliteStore


@dataclass(frozen=True)
class BacktestPaperDiffReport:
    account_id: str
    trade_date: date
    rebalance_trade_date: date | None
    status: str
    tolerance: float
    max_abs_weight_diff: float
    total_abs_weight_diff: float
    matched_count: int
    missing_in_paper_count: int
    missing_in_backtest_count: int
    order_count: int
    fill_count: int
    position_count: int
    differences: pd.DataFrame

    def to_dict(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "trade_date": self.trade_date.isoformat(),
            "rebalance_trade_date": self.rebalance_trade_date.isoformat()
            if self.rebalance_trade_date
            else None,
            "status": self.status,
            "tolerance": self.tolerance,
            "max_abs_weight_diff": self.max_abs_weight_diff,
            "total_abs_weight_diff": self.total_abs_weight_diff,
            "matched_count": self.matched_count,
            "missing_in_paper_count": self.missing_in_paper_count,
            "missing_in_backtest_count": self.missing_in_backtest_count,
            "order_count": self.order_count,
            "fill_count": self.fill_count,
            "position_count": self.position_count,
            "differences": self.differences.to_dict(orient="records"),
        }


def compare_backtest_to_paper(
    *,
    backtest_report_path: Path,
    paper_store_path: Path,
    trade_date: date,
    account_id: str = "paper",
    tolerance: float = 0.02,
) -> BacktestPaperDiffReport:
    backtest = _read_backtest_report(backtest_report_path)
    rebalance = _select_rebalance(backtest.get("rebalance_records", []), trade_date)
    target_weights = _target_weights_frame(rebalance)

    store = SqliteStore(paper_store_path)
    store.init_schema()
    positions = store.load_positions(account_id, trade_date)
    orders = store.load_order_intents(account_id, trade_date)
    fills = store.load_order_fills(account_id, trade_date)
    snapshot = store.load_portfolio_snapshot(account_id, trade_date)
    paper_weights = _paper_weights_frame(positions, snapshot_total_asset=snapshot.total_asset if snapshot else None)

    differences = _diff_weights(target_weights, paper_weights)
    max_abs = float(differences["abs_weight_diff"].max()) if not differences.empty else 0.0
    total_abs = float(differences["abs_weight_diff"].sum()) if not differences.empty else 0.0
    missing_in_paper = int((differences["paper_portfolio_weight"] == 0).sum())
    missing_in_backtest = int((differences["backtest_target_weight"] == 0).sum())
    matched = int(
        (
            (differences["paper_portfolio_weight"] > 0)
            & (differences["backtest_target_weight"] > 0)
        ).sum()
    )
    status = (
        "OK"
        if missing_in_paper == 0 and missing_in_backtest == 0 and max_abs <= tolerance
        else "DIFF"
    )
    rebalance_date = (
        pd.to_datetime(rebalance["trade_date"]).date()
        if rebalance and rebalance.get("trade_date")
        else None
    )
    return BacktestPaperDiffReport(
        account_id=account_id,
        trade_date=trade_date,
        rebalance_trade_date=rebalance_date,
        status=status,
        tolerance=tolerance,
        max_abs_weight_diff=max_abs,
        total_abs_weight_diff=total_abs,
        matched_count=matched,
        missing_in_paper_count=missing_in_paper,
        missing_in_backtest_count=missing_in_backtest,
        order_count=len(orders),
        fill_count=len(fills),
        position_count=len(positions),
        differences=differences,
    )


def write_diff_json(report: BacktestPaperDiffReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_diff_markdown(report: BacktestPaperDiffReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_diff_markdown(report), encoding="utf-8")
    return path


def render_diff_markdown(report: BacktestPaperDiffReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Trade Date", report.trade_date.isoformat()],
        ["Backtest Rebalance Date", report.rebalance_trade_date.isoformat() if report.rebalance_trade_date else "-"],
        ["Tolerance", _percent(report.tolerance)],
        ["Max Abs Weight Diff", _percent(report.max_abs_weight_diff)],
        ["Total Abs Weight Diff", _percent(report.total_abs_weight_diff)],
        ["Matched Codes", report.matched_count],
        ["Missing In Paper", report.missing_in_paper_count],
        ["Missing In Backtest", report.missing_in_backtest_count],
        ["Orders", report.order_count],
        ["Fills", report.fill_count],
        ["Positions", report.position_count],
    ]
    if report.differences.empty:
        detail = "_No differences to show._"
    else:
        rows = []
        for row in report.differences.head(30).itertuples(index=False):
            rows.append(
                [
                    row.ts_code,
                    _percent(row.backtest_target_weight),
                    _percent(row.paper_portfolio_weight),
                    _percent(row.weight_diff),
                    int(row.paper_quantity),
                ]
            )
        detail = _table(
            ["Code", "Backtest Weight", "Paper Weight", "Diff", "Paper Qty"],
            rows,
        )
    return "\n".join(
        [
            f"# Backtest vs Paper Diff - {report.trade_date.isoformat()}",
            "",
            "## Summary",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Weight Differences",
            detail,
            "",
        ]
    )


def _read_backtest_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"backtest report not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected backtest report JSON object: {path}")
    return data


def _select_rebalance(records: object, trade_date: date) -> dict[str, Any]:
    if not isinstance(records, list):
        return {}
    candidates = []
    for record in records:
        if not isinstance(record, dict) or not record.get("trade_date"):
            continue
        record_date = pd.to_datetime(record["trade_date"]).date()
        if record_date <= trade_date:
            candidates.append((record_date, record))
    if not candidates:
        return {}
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _target_weights_frame(rebalance: dict[str, Any]) -> pd.DataFrame:
    target_weights = rebalance.get("target_weights", []) if rebalance else []
    if not isinstance(target_weights, list) or not target_weights:
        return pd.DataFrame(columns=["ts_code", "backtest_target_weight"])
    rows = [
        {
            "ts_code": str(item.get("ts_code")),
            "backtest_target_weight": float(item.get("target_weight", 0.0)),
        }
        for item in target_weights
        if isinstance(item, dict) and item.get("ts_code")
    ]
    return pd.DataFrame(rows)


def _paper_weights_frame(
    positions: pd.DataFrame,
    *,
    snapshot_total_asset: float | None,
) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=["ts_code", "paper_portfolio_weight", "paper_quantity"])
    df = positions.copy()
    if snapshot_total_asset and snapshot_total_asset > 0 and "market_value" in df.columns:
        df["paper_portfolio_weight"] = df["market_value"].astype(float) / float(snapshot_total_asset)
    elif "weight" in df.columns:
        df["paper_portfolio_weight"] = df["weight"].astype(float)
    else:
        df["paper_portfolio_weight"] = 0.0
    df["paper_quantity"] = df["quantity"].astype(int)
    return df[["ts_code", "paper_portfolio_weight", "paper_quantity"]]


def _diff_weights(target_weights: pd.DataFrame, paper_weights: pd.DataFrame) -> pd.DataFrame:
    merged = target_weights.merge(paper_weights, on="ts_code", how="outer")
    if merged.empty:
        return pd.DataFrame(
            columns=[
                "ts_code",
                "backtest_target_weight",
                "paper_portfolio_weight",
                "weight_diff",
                "abs_weight_diff",
                "paper_quantity",
            ]
        )
    merged["backtest_target_weight"] = merged["backtest_target_weight"].fillna(0.0).astype(float)
    merged["paper_portfolio_weight"] = merged["paper_portfolio_weight"].fillna(0.0).astype(float)
    merged["paper_quantity"] = merged["paper_quantity"].fillna(0).astype(int)
    merged["weight_diff"] = merged["paper_portfolio_weight"] - merged["backtest_target_weight"]
    merged["abs_weight_diff"] = merged["weight_diff"].abs()
    return merged.sort_values(["abs_weight_diff", "ts_code"], ascending=[False, True]).reset_index(drop=True)


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"
