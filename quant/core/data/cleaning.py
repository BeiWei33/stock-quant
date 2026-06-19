from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DailyBarCleaningPolicy:
    fix_ohlc_envelope: bool = True
    flag_zero_volume: bool = True
    flag_non_positive_price: bool = True
    flag_non_positive_amount: bool = False
    diff_sample_limit: int = 20

    @classmethod
    def from_file(cls, path: Path) -> "DailyBarCleaningPolicy":
        if not path.exists():
            raise FileNotFoundError(f"cleaning config not found: {path}")
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
        else:
            try:
                import yaml  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError("PyYAML is required to read YAML cleaning config files") from exc
            payload = yaml.safe_load(text) or {}
        if not isinstance(payload, dict):
            raise ValueError("cleaning config must be a mapping")
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DailyBarCleaningPolicy":
        cleaning = payload.get("cleaning", payload)
        if not isinstance(cleaning, dict):
            raise ValueError("cleaning config must be a mapping")
        rules = cleaning.get("rules", {})
        if not isinstance(rules, dict):
            raise ValueError("cleaning.rules must be a mapping")
        return cls(
            fix_ohlc_envelope=_rule_enabled(rules, "ohlc_envelope", True),
            flag_zero_volume=_rule_enabled(rules, "zero_volume", True),
            flag_non_positive_price=_rule_enabled(rules, "non_positive_price", True),
            flag_non_positive_amount=_rule_enabled(rules, "non_positive_amount", False),
            diff_sample_limit=int(cleaning.get("diff_sample_limit", 20)),
        )

    def merge(self, overrides: dict[str, Any]) -> "DailyBarCleaningPolicy":
        values = asdict(self)
        for key, value in overrides.items():
            if value is not None:
                values[key] = value
        return DailyBarCleaningPolicy(**values)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DataCleaningDiff:
    ts_code: str
    trade_date: str
    field: str
    before: object
    after: object
    rule: str
    action: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DataCleaningReport:
    input_rows: int
    output_rows: int
    changed_row_count: int
    high_fixed_count: int
    low_fixed_count: int
    non_positive_volume_count: int
    non_positive_amount_count: int
    auto_fixed_row_count: int = 0
    manual_review_row_count: int = 0
    rule_counts: dict[str, int] | None = None
    diffs: list[DataCleaningDiff] | None = None
    policy: DailyBarCleaningPolicy | None = None

    @property
    def changed_rows(self) -> int:
        return self.changed_row_count

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["changed_rows"] = self.changed_rows
        data["rule_counts"] = self.rule_counts or {}
        data["diffs"] = [diff.to_dict() for diff in self.diffs or []]
        data["policy"] = self.policy.to_dict() if self.policy else {}
        return data


class DailyBarCleaner:
    """Conservative deterministic cleaner for daily OHLCV bars."""

    def __init__(self, policy: DailyBarCleaningPolicy | None = None) -> None:
        self.policy = policy or DailyBarCleaningPolicy()

    def clean(self, bars: pd.DataFrame) -> tuple[pd.DataFrame, DataCleaningReport]:
        if bars.empty:
            return bars.copy(), DataCleaningReport(
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                rule_counts={},
                diffs=[],
                policy=self.policy,
            )
        df = bars.copy()
        for column in ["open", "high", "low", "close", "volume", "amount"]:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
        if "quality_flag" not in df.columns:
            df["quality_flag"] = "NORMAL"
        else:
            df["quality_flag"] = df["quality_flag"].fillna("NORMAL")

        price_columns = ["open", "high", "low", "close"]
        envelope_high = df[price_columns].max(axis=1)
        envelope_low = df[price_columns].min(axis=1)
        high_needs_fix = df["high"].notna() & envelope_high.notna() & (df["high"] < envelope_high)
        low_needs_fix = df["low"].notna() & envelope_low.notna() & (df["low"] > envelope_low)
        non_positive_price = (df[price_columns] <= 0).any(axis=1)
        non_positive_volume = df["volume"].fillna(0) <= 0
        non_positive_amount = df["amount"].fillna(0) <= 0
        diffs: list[DataCleaningDiff] = []

        if self.policy.fix_ohlc_envelope:
            _append_value_diffs(
                df,
                diffs,
                high_needs_fix,
                "high",
                envelope_high,
                "ohlc_envelope",
                "AUTO_FIX",
                self.policy.diff_sample_limit,
            )
            _append_value_diffs(
                df,
                diffs,
                low_needs_fix,
                "low",
                envelope_low,
                "ohlc_envelope",
                "AUTO_FIX",
                self.policy.diff_sample_limit,
            )
            df.loc[high_needs_fix, "high"] = envelope_high[high_needs_fix]
            df.loc[low_needs_fix, "low"] = envelope_low[low_needs_fix]
        else:
            high_needs_fix = high_needs_fix & False
            low_needs_fix = low_needs_fix & False

        zero_volume_flagged = non_positive_volume & self.policy.flag_zero_volume
        if self.policy.flag_zero_volume:
            _append_flag_diffs(
                df,
                diffs,
                zero_volume_flagged,
                "ZERO_VOLUME",
                "zero_volume",
                "MANUAL_REVIEW",
                self.policy.diff_sample_limit,
            )
            df.loc[zero_volume_flagged, "quality_flag"] = "ZERO_VOLUME"

        bad_price_flagged = non_positive_price & self.policy.flag_non_positive_price
        if self.policy.flag_non_positive_price:
            _append_flag_diffs(
                df,
                diffs,
                bad_price_flagged,
                "MANUAL_REVIEW",
                "non_positive_price",
                "MANUAL_REVIEW",
                self.policy.diff_sample_limit,
            )
            df.loc[bad_price_flagged, "quality_flag"] = "MANUAL_REVIEW"

        bad_amount_flagged = non_positive_amount & self.policy.flag_non_positive_amount
        if self.policy.flag_non_positive_amount:
            _append_flag_diffs(
                df,
                diffs,
                bad_amount_flagged,
                "MANUAL_REVIEW",
                "non_positive_amount",
                "MANUAL_REVIEW",
                self.policy.diff_sample_limit,
            )
            df.loc[bad_amount_flagged, "quality_flag"] = "MANUAL_REVIEW"

        auto_fixed_rows = high_needs_fix | low_needs_fix
        manual_review_rows = zero_volume_flagged | bad_price_flagged | bad_amount_flagged
        changed_rows = auto_fixed_rows | manual_review_rows

        report = DataCleaningReport(
            input_rows=len(bars),
            output_rows=len(df),
            changed_row_count=int(changed_rows.sum()),
            high_fixed_count=int(high_needs_fix.sum()),
            low_fixed_count=int(low_needs_fix.sum()),
            non_positive_volume_count=int(non_positive_volume.sum()),
            non_positive_amount_count=int(non_positive_amount.sum()),
            auto_fixed_row_count=int(auto_fixed_rows.sum()),
            manual_review_row_count=int(manual_review_rows.sum()),
            rule_counts={
                "ohlc_envelope_high": int(high_needs_fix.sum()),
                "ohlc_envelope_low": int(low_needs_fix.sum()),
                "zero_volume": int(zero_volume_flagged.sum()),
                "non_positive_price": int(bad_price_flagged.sum()),
                "non_positive_amount": int(bad_amount_flagged.sum()),
            },
            diffs=diffs,
            policy=self.policy,
        )
        return df, report


def write_cleaning_report(report: DataCleaningReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_cleaning_markdown(report: DataCleaningReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_cleaning_markdown(report), encoding="utf-8")
    return path


def render_cleaning_markdown(report: DataCleaningReport) -> str:
    summary_rows = [
        ["Input Rows", report.input_rows],
        ["Output Rows", report.output_rows],
        ["Changed Rows", report.changed_rows],
        ["Auto Fixed Rows", report.auto_fixed_row_count],
        ["Manual Review Rows", report.manual_review_row_count],
        ["High Fixed", report.high_fixed_count],
        ["Low Fixed", report.low_fixed_count],
        ["Non-positive Volume", report.non_positive_volume_count],
        ["Non-positive Amount", report.non_positive_amount_count],
    ]
    rule_rows = [[name, count] for name, count in (report.rule_counts or {}).items()]
    diff_rows = [
        [
            diff.ts_code,
            diff.trade_date,
            diff.field,
            diff.before,
            diff.after,
            diff.rule,
            diff.action,
        ]
        for diff in report.diffs or []
    ]
    return "\n".join(
        [
            "# Data Cleaning Report",
            "",
            "## Summary",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Rule Counts",
            _table(["Rule", "Count"], rule_rows) if rule_rows else "_No rule actions._",
            "",
            "## Before/After Samples",
            _table(["Code", "Date", "Field", "Before", "After", "Rule", "Action"], diff_rows)
            if diff_rows
            else "_No sampled changes._",
            "",
        ]
    )


def _rule_enabled(rules: dict[str, Any], name: str, default: bool) -> bool:
    value = rules.get(name, default)
    if isinstance(value, dict):
        return bool(value.get("enabled", default))
    return bool(value)


def _append_value_diffs(
    df: pd.DataFrame,
    diffs: list[DataCleaningDiff],
    mask: pd.Series,
    field: str,
    after_values: pd.Series,
    rule: str,
    action: str,
    limit: int,
) -> None:
    remaining = max(limit - len(diffs), 0)
    if remaining <= 0:
        return
    for index in df.index[mask][:remaining]:
        diffs.append(
            DataCleaningDiff(
                ts_code=str(df.at[index, "ts_code"]) if "ts_code" in df.columns else "",
                trade_date=_date_value(df.at[index, "trade_date"]) if "trade_date" in df.columns else "",
                field=field,
                before=_json_value(df.at[index, field]),
                after=_json_value(after_values.at[index]),
                rule=rule,
                action=action,
            )
        )


def _append_flag_diffs(
    df: pd.DataFrame,
    diffs: list[DataCleaningDiff],
    mask: pd.Series,
    after: str,
    rule: str,
    action: str,
    limit: int,
) -> None:
    remaining = max(limit - len(diffs), 0)
    if remaining <= 0:
        return
    changed = mask & (df["quality_flag"].astype(str) != after)
    for index in df.index[changed][:remaining]:
        diffs.append(
            DataCleaningDiff(
                ts_code=str(df.at[index, "ts_code"]) if "ts_code" in df.columns else "",
                trade_date=_date_value(df.at[index, "trade_date"]) if "trade_date" in df.columns else "",
                field="quality_flag",
                before=str(df.at[index, "quality_flag"]),
                after=after,
                rule=rule,
                action=action,
            )
        )


def _date_value(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _json_value(value: object) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
