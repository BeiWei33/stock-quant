from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.data.cleaning import (
    DailyBarCleaner,
    DailyBarCleaningPolicy,
    render_cleaning_markdown,
    write_cleaning_markdown,
    write_cleaning_report,
)
from quant.core.data.quality import DataQualityAnalyzer


def test_daily_bar_cleaner_fixes_ohlc_envelope() -> None:
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 2),
                "adj_type": "qfq",
                "open": 10.0,
                "high": 9.0,
                "low": 11.0,
                "close": 10.5,
                "volume": 100,
                "amount": 1000,
                "quality_flag": "NORMAL",
            }
        ]
    )

    cleaned, report = DailyBarCleaner().clean(bars)

    assert cleaned.iloc[0]["high"] == 11.0
    assert cleaned.iloc[0]["low"] == 9.0
    assert report.high_fixed_count == 1
    assert report.low_fixed_count == 1
    assert report.auto_fixed_row_count == 1
    assert report.rule_counts["ohlc_envelope_high"] == 1
    assert report.diffs[0].action == "AUTO_FIX"
    quality = DataQualityAnalyzer(check_weekday_gaps=False).analyze(cleaned)
    assert quality.ok


def test_daily_bar_cleaner_marks_zero_volume_without_fabricating_volume() -> None:
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 2),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 0,
                "amount": 0,
            }
        ]
    )

    cleaned, report = DailyBarCleaner().clean(bars)

    assert cleaned.iloc[0]["volume"] == 0
    assert cleaned.iloc[0]["quality_flag"] == "ZERO_VOLUME"
    assert report.non_positive_volume_count == 1
    assert report.manual_review_row_count == 1
    assert report.rule_counts["zero_volume"] == 1


def test_daily_bar_cleaner_can_disable_ohlc_auto_fix() -> None:
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 2),
                "open": 10.0,
                "high": 9.0,
                "low": 11.0,
                "close": 10.5,
                "volume": 100,
                "amount": 1000,
            }
        ]
    )

    cleaned, report = DailyBarCleaner(
        DailyBarCleaningPolicy(fix_ohlc_envelope=False)
    ).clean(bars)

    assert cleaned.iloc[0]["high"] == 9.0
    assert cleaned.iloc[0]["low"] == 11.0
    assert report.high_fixed_count == 0
    assert report.low_fixed_count == 0
    assert report.policy is not None
    assert not report.policy.fix_ohlc_envelope


def test_daily_bar_cleaning_policy_loads_rule_switches(tmp_path) -> None:
    config_path = tmp_path / "cleaning.yaml"
    config_path.write_text(
        "\n".join(
            [
                "cleaning:",
                "  diff_sample_limit: 3",
                "  rules:",
                "    ohlc_envelope:",
                "      enabled: false",
                "    zero_volume:",
                "      enabled: false",
                "    non_positive_amount:",
                "      enabled: true",
            ]
        ),
        encoding="utf-8",
    )

    policy = DailyBarCleaningPolicy.from_file(config_path)

    assert not policy.fix_ohlc_envelope
    assert not policy.flag_zero_volume
    assert policy.flag_non_positive_amount
    assert policy.diff_sample_limit == 3


def test_write_cleaning_report(tmp_path) -> None:
    _, report = DailyBarCleaner().clean(pd.DataFrame())
    path = write_cleaning_report(report, tmp_path / "cleaning.json")

    assert '"input_rows": 0' in path.read_text(encoding="utf-8")
    markdown_path = write_cleaning_markdown(report, tmp_path / "cleaning.md")
    assert "Data Cleaning Report" in markdown_path.read_text(encoding="utf-8")
    assert "Before/After Samples" in render_cleaning_markdown(report)
