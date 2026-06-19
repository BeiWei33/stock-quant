from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class MonitorStatusSummary:
    latest_trade_date: str
    latest_run_id: str
    latest_status: str
    latest_ok: bool
    total_runs: int
    success_runs: int
    warning_runs: int
    failed_runs: int
    success_rate: float
    consecutive_unhealthy_runs: int
    latest_total_asset: float
    latest_daily_return: float
    latest_drawdown: float
    max_drawdown: float
    latest_position_ratio: float
    total_orders: int
    total_rejected_orders: int
    total_fills: int
    total_rejected_fills: int
    latest_data_quality_level: str
    data_quality_error_runs: int
    data_quality_warning_runs: int
    data_quality_issue_count: int
    data_cleaning_changed_rows: int
    latest_reconciliation_status: str
    reconciliation_diff_runs: int
    reconciliation_diff_count: int
    latest_risk_guard_status: str
    risk_guard_rejected_runs: int
    risk_guard_rejected_orders: int
    latest_pretrade_gate_status: str
    latest_pretrade_gate_passed: bool
    pretrade_gate_block_runs: int
    pretrade_gate_failed_count: int
    pretrade_gate_failed_checks: str
    failed_health_count: int
    failed_health_checks: str
    history_path: str

    @property
    def level(self) -> str:
        if self.failed_runs > 0 or self.consecutive_unhealthy_runs >= 2:
            return "CRITICAL"
        if (
            not self.latest_ok
            or self.warning_runs > 0
            or self.failed_health_count > 0
            or self.data_quality_error_runs > 0
            or self.data_quality_warning_runs > 0
            or self.reconciliation_diff_runs > 0
            or self.risk_guard_rejected_runs > 0
        ):
            return "WARNING"
        return "INFO"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["level"] = self.level
        return data


class MonitorStatusBuilder:
    def __init__(
        self,
        history_path: Path,
        limit: int = 20,
        latest_per_trade_date: bool = True,
    ) -> None:
        self.history_path = history_path
        self.limit = limit
        self.latest_per_trade_date = latest_per_trade_date

    def build(self) -> MonitorStatusSummary:
        if not self.history_path.exists():
            raise FileNotFoundError(f"monitoring history not found: {self.history_path}")
        df = pd.read_csv(self.history_path)
        if df.empty:
            raise ValueError(f"monitoring history is empty: {self.history_path}")
        df = _normalize(df).sort_values(
            ["trade_date", "recorded_at", "run_id"], na_position="first"
        )
        if self.latest_per_trade_date:
            df = df.groupby("trade_date", as_index=False, sort=False).tail(1)
        window = df.tail(self.limit) if self.limit > 0 else df
        latest = window.iloc[-1]
        unhealthy = ~_healthy_mask(window)
        return MonitorStatusSummary(
            latest_trade_date=str(latest["trade_date"]),
            latest_run_id=str(latest["run_id"]),
            latest_status=str(latest["run_status"]),
            latest_ok=bool(latest["ok"]),
            total_runs=len(window),
            success_runs=int((window["run_status"].eq("SUCCESS") & window["ok"]).sum()),
            warning_runs=int((window["run_status"].isin(["CHECK", "WARNING"]) | (~window["ok"])).sum()),
            failed_runs=int(window["run_status"].eq("FAILED").sum()),
            success_rate=float((window["run_status"].eq("SUCCESS") & window["ok"]).mean()),
            consecutive_unhealthy_runs=_count_trailing_true(unhealthy.tolist()),
            latest_total_asset=float(latest["total_asset"]),
            latest_daily_return=float(latest["daily_return"]),
            latest_drawdown=float(latest["drawdown"]),
            max_drawdown=float(window["drawdown"].min()),
            latest_position_ratio=float(latest["total_position_ratio"]),
            total_orders=int(window["order_count"].sum()),
            total_rejected_orders=int(window["rejected_order_count"].sum()),
            total_fills=int(window["fill_count"].sum()),
            total_rejected_fills=int(window["fill_rejected_count"].sum()),
            latest_data_quality_level=str(latest["data_quality_level"]),
            data_quality_error_runs=int(window["data_quality_level"].eq("ERROR").sum()),
            data_quality_warning_runs=int(window["data_quality_level"].eq("WARNING").sum()),
            data_quality_issue_count=int(window["data_quality_issue_count"].sum()),
            data_cleaning_changed_rows=int(window["data_cleaning_changed_rows"].sum()),
            latest_reconciliation_status=str(latest["reconciliation_status"]),
            reconciliation_diff_runs=int(window["reconciliation_status"].eq("DIFF").sum()),
            reconciliation_diff_count=int(window["reconciliation_diff_count"].sum()),
            latest_risk_guard_status=str(latest["risk_guard_status"]),
            risk_guard_rejected_runs=int(window["risk_guard_status"].eq("REJECTED").sum()),
            risk_guard_rejected_orders=int(window["risk_guard_rejected_orders"].sum()),
            latest_pretrade_gate_status=str(latest["pretrade_gate_status"]),
            latest_pretrade_gate_passed=bool(latest["pretrade_gate_passed"]),
            pretrade_gate_block_runs=int(window["pretrade_gate_status"].eq("BLOCK").sum()),
            pretrade_gate_failed_count=int(window["pretrade_gate_failed_count"].sum()),
            pretrade_gate_failed_checks=_join_failed_checks(window["pretrade_gate_failed_checks"]),
            failed_health_count=int(window["failed_health_count"].sum()),
            failed_health_checks=_join_failed_checks(window["failed_health_checks"]),
            history_path=str(self.history_path),
        )


def write_status_json(summary: MonitorStatusSummary, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_status_markdown(summary: MonitorStatusSummary, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_status_markdown(summary), encoding="utf-8")
    return path


def render_status_markdown(summary: MonitorStatusSummary) -> str:
    rows = [
        ["Level", summary.level],
        ["Latest Trade Date", summary.latest_trade_date],
        ["Latest Run Status", summary.latest_status],
        ["Latest OK", summary.latest_ok],
        ["Runs In Window", summary.total_runs],
        ["Success Rate", _percent(summary.success_rate)],
        ["Consecutive Unhealthy Runs", summary.consecutive_unhealthy_runs],
        ["Latest Total Asset", _money(summary.latest_total_asset)],
        ["Latest Daily Return", _percent(summary.latest_daily_return)],
        ["Latest Drawdown", _percent(summary.latest_drawdown)],
        ["Max Drawdown", _percent(summary.max_drawdown)],
        ["Latest Position Ratio", _percent(summary.latest_position_ratio)],
        ["Orders", f"{summary.total_orders} accepted, {summary.total_rejected_orders} rejected"],
        ["Fills", f"{summary.total_fills} filled, {summary.total_rejected_fills} rejected"],
        ["Latest Data Quality", summary.latest_data_quality_level],
        ["Data Quality Error Runs", summary.data_quality_error_runs],
        ["Data Quality Warning Runs", summary.data_quality_warning_runs],
        ["Data Quality Issues", summary.data_quality_issue_count],
        ["Cleaned Rows", summary.data_cleaning_changed_rows],
        ["Latest Reconciliation", summary.latest_reconciliation_status],
        ["Reconciliation Diff Runs", summary.reconciliation_diff_runs],
        ["Reconciliation Diffs", summary.reconciliation_diff_count],
        ["Latest Risk Guard", summary.latest_risk_guard_status],
        ["Risk Guard Rejected Runs", summary.risk_guard_rejected_runs],
        ["Risk Guard Rejected Orders", summary.risk_guard_rejected_orders],
        ["Latest Pre-Trade Gate", summary.latest_pretrade_gate_status],
        ["Pre-Trade Gate Passed", summary.latest_pretrade_gate_passed],
        ["Pre-Trade Gate Block Runs", summary.pretrade_gate_block_runs],
        ["Pre-Trade Gate Failed Checks", summary.pretrade_gate_failed_checks or "-"],
        ["Failed Health Checks", summary.failed_health_checks or "-"],
    ]
    return "\n".join(
        [
            f"# Quant Monitor Status - {summary.latest_trade_date}",
            "",
            _table(["Metric", "Value"], rows),
            "",
            f"History: `{summary.history_path}`",
            "",
        ]
    )


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    defaults: dict[str, object] = {
        "run_id": "",
        "recorded_at": "",
        "run_status": "UNKNOWN",
        "ok": False,
        "total_asset": 0.0,
        "daily_return": 0.0,
        "drawdown": 0.0,
        "total_position_ratio": 0.0,
        "order_count": 0,
        "rejected_order_count": 0,
        "fill_count": 0,
        "fill_rejected_count": 0,
        "data_quality_level": "UNKNOWN",
        "data_quality_issue_count": 0,
        "data_cleaning_changed_rows": 0,
        "reconciliation_status": "UNKNOWN",
        "reconciliation_diff_count": 0,
        "risk_guard_status": "UNKNOWN",
        "risk_guard_rejected_orders": 0,
        "pretrade_gate_status": "UNKNOWN",
        "pretrade_gate_passed": False,
        "pretrade_gate_failed_count": 0,
        "pretrade_gate_failed_checks": "",
        "failed_health_count": 0,
        "failed_health_checks": "",
    }
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date.astype(str)
    df["recorded_at"] = pd.to_datetime(df["recorded_at"], errors="coerce", utc=True)
    df["run_id"] = df["run_id"].fillna("").astype(str)
    df["recorded_at"] = df["recorded_at"].fillna(pd.Timestamp("1900-01-01", tz="UTC"))
    df["run_status"] = df["run_status"].fillna("UNKNOWN").astype(str).str.upper()
    df["ok"] = df["ok"].map(_bool_value)
    numeric_columns = [
        "total_asset",
        "daily_return",
        "drawdown",
        "total_position_ratio",
        "order_count",
        "rejected_order_count",
        "fill_count",
        "fill_rejected_count",
        "data_quality_issue_count",
        "data_cleaning_changed_rows",
        "reconciliation_diff_count",
        "risk_guard_rejected_orders",
        "pretrade_gate_failed_count",
        "failed_health_count",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    df["data_quality_level"] = df["data_quality_level"].fillna("UNKNOWN").astype(str).str.upper()
    df["reconciliation_status"] = df["reconciliation_status"].fillna("UNKNOWN").astype(str).str.upper()
    df["risk_guard_status"] = df["risk_guard_status"].fillna("UNKNOWN").astype(str).str.upper()
    df["pretrade_gate_status"] = df["pretrade_gate_status"].fillna("UNKNOWN").astype(str).str.upper()
    df["pretrade_gate_passed"] = df["pretrade_gate_passed"].map(_bool_value)
    df["pretrade_gate_failed_checks"] = df["pretrade_gate_failed_checks"].fillna("").astype(str)
    df["failed_health_checks"] = df["failed_health_checks"].fillna("").astype(str)
    return df


def _healthy_mask(df: pd.DataFrame) -> pd.Series:
    return (
        df["run_status"].eq("SUCCESS")
        & df["ok"]
        & df["failed_health_count"].eq(0)
    )


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _count_trailing_true(values: list[bool]) -> int:
    count = 0
    for value in reversed(values):
        if not value:
            break
        count += 1
    return count


def _join_failed_checks(values: pd.Series) -> str:
    names: list[str] = []
    for value in values:
        if value is None or pd.isna(value):
            continue
        for name in str(value).split(";"):
            name = name.strip()
            if name and name not in names:
                names.append(name)
    return ";".join(names)


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"
