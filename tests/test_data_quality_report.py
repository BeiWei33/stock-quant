from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.data.quality import (
    DataQualityAnalyzer,
    render_quality_markdown,
    write_quality_json,
    write_quality_markdown,
)


def test_data_quality_report_passes_clean_bars() -> None:
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 1),
                "adj_type": "qfq",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 100,
                "amount": 1000,
                "quality_flag": "NORMAL",
            },
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 2),
                "adj_type": "qfq",
                "open": 10.5,
                "high": 11,
                "low": 10,
                "close": 10.8,
                "volume": 100,
                "amount": 1000,
                "quality_flag": "NORMAL",
            },
        ]
    )
    stocks = pd.DataFrame([{"ts_code": "000001.SZ"}])

    report = DataQualityAnalyzer(check_weekday_gaps=True).analyze(bars=bars, stocks=stocks)

    assert report.ok
    assert report.level == "INFO"
    assert report.bar_count == 2
    assert report.issues == []


def test_data_quality_report_detects_invalid_bars() -> None:
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 1),
                "adj_type": "qfq",
                "open": 10,
                "high": 9,
                "low": 8,
                "close": 10,
                "volume": 0,
                "amount": 0,
                "quality_flag": "ZERO_VOLUME",
            },
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 1),
                "adj_type": "qfq",
                "open": -1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 10,
                "amount": 100,
                "quality_flag": "NORMAL",
            },
            {
                "ts_code": "000002.SZ",
                "trade_date": date(2024, 1, 2),
                "adj_type": "qfq",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10,
                "volume": 10,
                "amount": 100,
                "quality_flag": "NORMAL",
            },
        ]
    )
    stocks = pd.DataFrame([{"ts_code": "000001.SZ"}])

    report = DataQualityAnalyzer(check_weekday_gaps=False).analyze(bars=bars, stocks=stocks)
    issue_types = {issue.issue_type for issue in report.issues}

    assert not report.ok
    assert report.level == "ERROR"
    assert "DUPLICATE_BAR_KEY" in issue_types
    assert "NON_POSITIVE_PRICE" in issue_types
    assert "OHLC_INCONSISTENT" in issue_types
    assert "NON_POSITIVE_VOLUME" in issue_types
    assert "NON_POSITIVE_AMOUNT" in issue_types
    assert "QUALITY_FLAG_REVIEW" in issue_types
    assert "BAR_CODE_NOT_IN_STOCK_MASTER" in issue_types


def test_data_quality_report_writes_json_and_markdown(tmp_path) -> None:
    bars = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": date(2024, 1, 1),
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10,
                "volume": 100,
                "amount": 1000,
            }
        ]
    )
    report = DataQualityAnalyzer(check_weekday_gaps=False).analyze(bars=bars)
    json_path = write_quality_json(report, tmp_path / "quality.json")
    markdown_path = write_quality_markdown(report, tmp_path / "quality.md")

    assert '"level": "INFO"' in json_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Data Quality Report" in markdown
    assert "No data quality issues" in render_quality_markdown(report)
