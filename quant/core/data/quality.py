from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class DataQualityIssue:
    issue_type: str
    severity: str
    count: int
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DataQualityReport:
    bar_count: int
    stock_count: int
    code_count: int
    trading_days: int
    start_date: str
    end_date: str
    issues: list[DataQualityIssue]

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "ERROR" for issue in self.issues)

    @property
    def level(self) -> str:
        if any(issue.severity == "ERROR" for issue in self.issues):
            return "ERROR"
        if self.issues:
            return "WARNING"
        return "INFO"

    def to_dict(self) -> dict[str, object]:
        return {
            "bar_count": self.bar_count,
            "stock_count": self.stock_count,
            "code_count": self.code_count,
            "trading_days": self.trading_days,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "ok": self.ok,
            "level": self.level,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class DataQualityAnalyzer:
    def __init__(self, *, check_weekday_gaps: bool = True) -> None:
        self.check_weekday_gaps = check_weekday_gaps

    def analyze(self, bars: pd.DataFrame, stocks: pd.DataFrame | None = None) -> DataQualityReport:
        bars = _normalize_bars_for_quality(bars)
        stocks = stocks.copy() if stocks is not None else pd.DataFrame()
        if bars.empty:
            return DataQualityReport(
                bar_count=0,
                stock_count=len(stocks),
                code_count=0,
                trading_days=0,
                start_date="",
                end_date="",
                issues=[DataQualityIssue("EMPTY_BARS", "ERROR", 1, "daily_bar is empty")],
            )

        issues: list[DataQualityIssue] = []
        issues.extend(_duplicate_key_issues(bars))
        issues.extend(_price_issues(bars))
        issues.extend(_volume_amount_issues(bars))
        issues.extend(_quality_flag_issues(bars))
        if stocks is not None and not stocks.empty:
            issues.extend(_stock_master_issues(bars, stocks))
        if self.check_weekday_gaps:
            issues.extend(_weekday_gap_issues(bars))

        dates = pd.to_datetime(bars["trade_date"]).dt.date
        return DataQualityReport(
            bar_count=len(bars),
            stock_count=len(stocks),
            code_count=int(bars["ts_code"].nunique()),
            trading_days=int(dates.nunique()),
            start_date=min(dates).isoformat(),
            end_date=max(dates).isoformat(),
            issues=issues,
        )


def add_basic_quality_flags(bars: pd.DataFrame) -> pd.DataFrame:
    """Mark obvious quality states without deleting rows."""
    df = bars.copy()
    flags = df.get("quality_flag", "NORMAL")
    df["quality_flag"] = flags.fillna("NORMAL") if hasattr(flags, "fillna") else flags

    zero_volume = df["volume"].fillna(0) <= 0
    bad_price = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)

    df.loc[zero_volume, "quality_flag"] = "ZERO_VOLUME"
    df.loc[bad_price, "quality_flag"] = "MANUAL_REVIEW"
    return df


def write_quality_json(report: DataQualityReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_quality_markdown(report: DataQualityReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_quality_markdown(report), encoding="utf-8")
    return path


def render_quality_markdown(report: DataQualityReport) -> str:
    summary_rows = [
        ["Level", report.level],
        ["OK", report.ok],
        ["Bars", report.bar_count],
        ["Stocks", report.stock_count],
        ["Codes", report.code_count],
        ["Trading Days", report.trading_days],
        ["Start Date", report.start_date or "-"],
        ["End Date", report.end_date or "-"],
    ]
    if report.issues:
        issue_rows = [
            [issue.issue_type, issue.severity, issue.count, issue.detail] for issue in report.issues
        ]
        issue_section = _table(["Issue", "Severity", "Count", "Detail"], issue_rows)
    else:
        issue_section = "_No data quality issues found._"
    return "\n".join(
        [
            f"# Data Quality Report - {report.end_date or 'N/A'}",
            "",
            "## Summary",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Issues",
            issue_section,
            "",
        ]
    )


def _normalize_bars_for_quality(bars: pd.DataFrame) -> pd.DataFrame:
    df = bars.copy()
    if df.empty:
        return df
    if "adj_type" not in df.columns:
        df["adj_type"] = "none"
    if "quality_flag" not in df.columns:
        df["quality_flag"] = "NORMAL"
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
    for column in ["open", "high", "low", "close", "volume", "amount"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _duplicate_key_issues(bars: pd.DataFrame) -> list[DataQualityIssue]:
    duplicated = bars.duplicated(["ts_code", "trade_date", "adj_type"], keep=False)
    if not duplicated.any():
        return []
    samples = _sample_keys(bars.loc[duplicated])
    return [
        DataQualityIssue(
            "DUPLICATE_BAR_KEY",
            "ERROR",
            int(duplicated.sum()),
            f"samples={samples}",
        )
    ]


def _price_issues(bars: pd.DataFrame) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    price_columns = ["open", "high", "low", "close"]
    missing_price = bars[price_columns].isna().any(axis=1)
    if missing_price.any():
        issues.append(
            DataQualityIssue(
                "MISSING_PRICE",
                "ERROR",
                int(missing_price.sum()),
                f"samples={_sample_keys(bars.loc[missing_price])}",
            )
        )
    non_positive = (bars[price_columns] <= 0).any(axis=1)
    if non_positive.any():
        issues.append(
            DataQualityIssue(
                "NON_POSITIVE_PRICE",
                "ERROR",
                int(non_positive.sum()),
                f"samples={_sample_keys(bars.loc[non_positive])}",
            )
        )
    valid = bars[price_columns].notna().all(axis=1)
    inconsistent = valid & (
        (bars["high"] < bars[["open", "low", "close"]].max(axis=1))
        | (bars["low"] > bars[["open", "high", "close"]].min(axis=1))
    )
    if inconsistent.any():
        issues.append(
            DataQualityIssue(
                "OHLC_INCONSISTENT",
                "ERROR",
                int(inconsistent.sum()),
                f"samples={_sample_keys(bars.loc[inconsistent])}",
            )
        )
    return issues


def _volume_amount_issues(bars: pd.DataFrame) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    non_positive_volume = bars["volume"].fillna(0) <= 0
    if non_positive_volume.any():
        issues.append(
            DataQualityIssue(
                "NON_POSITIVE_VOLUME",
                "WARNING",
                int(non_positive_volume.sum()),
                f"samples={_sample_keys(bars.loc[non_positive_volume])}",
            )
        )
    non_positive_amount = bars["amount"].fillna(0) <= 0
    if non_positive_amount.any():
        issues.append(
            DataQualityIssue(
                "NON_POSITIVE_AMOUNT",
                "WARNING",
                int(non_positive_amount.sum()),
                f"samples={_sample_keys(bars.loc[non_positive_amount])}",
            )
        )
    return issues


def _quality_flag_issues(bars: pd.DataFrame) -> list[DataQualityIssue]:
    flagged = bars["quality_flag"].fillna("NORMAL").astype(str) != "NORMAL"
    if not flagged.any():
        return []
    counts = bars.loc[flagged, "quality_flag"].astype(str).value_counts().to_dict()
    detail = ";".join(f"{name}={count}" for name, count in counts.items())
    return [DataQualityIssue("QUALITY_FLAG_REVIEW", "WARNING", int(flagged.sum()), detail)]


def _stock_master_issues(bars: pd.DataFrame, stocks: pd.DataFrame) -> list[DataQualityIssue]:
    if "ts_code" not in stocks.columns:
        return [DataQualityIssue("STOCK_MASTER_MISSING_CODE", "ERROR", 1, "stocks missing ts_code")]
    missing = sorted(set(bars["ts_code"].astype(str)) - set(stocks["ts_code"].astype(str)))
    if not missing:
        return []
    return [
        DataQualityIssue(
            "BAR_CODE_NOT_IN_STOCK_MASTER",
            "ERROR",
            len(missing),
            f"samples={','.join(missing[:5])}",
        )
    ]


def _weekday_gap_issues(bars: pd.DataFrame) -> list[DataQualityIssue]:
    dates = pd.to_datetime(bars["trade_date"], errors="coerce")
    if dates.isna().any() or dates.empty:
        return []
    expected_dates = pd.bdate_range(dates.min(), dates.max()).date
    codes = sorted(bars["ts_code"].astype(str).unique())
    observed = {
        (str(row.ts_code), row.trade_date)
        for row in bars[["ts_code", "trade_date"]].drop_duplicates().itertuples(index=False)
    }
    missing: list[str] = []
    for code in codes:
        for trade_date in expected_dates:
            if (code, trade_date) not in observed:
                missing.append(f"{code}@{trade_date.isoformat()}")
                if len(missing) >= 5:
                    break
        if len(missing) >= 5:
            break
    missing_count = len(codes) * len(expected_dates) - len(observed)
    if missing_count <= 0:
        return []
    return [
        DataQualityIssue(
            "WEEKDAY_BAR_GAP",
            "WARNING",
            int(missing_count),
            f"samples={','.join(missing)}",
        )
    ]


def _sample_keys(df: pd.DataFrame, limit: int = 5) -> str:
    samples = []
    for row in df[["ts_code", "trade_date"]].head(limit).itertuples(index=False):
        trade_date = row.trade_date.isoformat() if hasattr(row.trade_date, "isoformat") else row.trade_date
        samples.append(f"{row.ts_code}@{trade_date}")
    return ",".join(samples)


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
