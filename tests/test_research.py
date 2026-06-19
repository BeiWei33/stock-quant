from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from quant.core.factor.technical import MomentumFactor
from quant.core.research.alpha_validation import forward_returns, validate_factor
from quant.core.research.factor_factory import build_factor
from quant.core.research.report import AlphaResearchReportWriter


def _bars() -> pd.DataFrame:
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(120)]
    dates = [d for d in dates if d.weekday() < 5]
    rows = []
    for idx, code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ", "000005.SZ"]):
        price = 10.0
        for trade_date in dates:
            price *= 1.0 + 0.001 * (idx + 1)
            rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date,
                    "adj_type": "qfq",
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1_000_000,
                    "amount": 100_000_000,
                    "quality_flag": "NORMAL",
                }
            )
    return pd.DataFrame(rows)


def test_forward_returns_emits_expected_columns() -> None:
    result = forward_returns(_bars(), horizon=5)

    assert {"trade_date", "ts_code", "forward_return"}.issubset(result.columns)
    assert not result.empty


def test_validate_factor_returns_summary_groups_and_turnover() -> None:
    bars = _bars()
    factor = MomentumFactor(20)
    factor_values = factor.calculate(bars)

    result = validate_factor(bars, factor_values, factor.name, horizon=5, quantiles=5, train_ratio=0.6)

    assert result.summary["sample_days"] > 0
    assert "rank_ic_mean" in result.summary
    assert "oos_rank_ic_mean" in result.summary
    assert result.split_summary["train"]["sample_days"] > 0
    assert result.split_summary["test"]["sample_days"] > 0
    assert not result.group_returns.empty
    assert not result.turnover.empty


def test_report_writer_outputs_json_and_markdown(tmp_path) -> None:
    bars = _bars()
    factor = build_factor("momentum_20d")
    result = validate_factor(bars, factor.calculate(bars), factor.name, horizon=5, quantiles=5)

    paths = AlphaResearchReportWriter().write(result, tmp_path)

    assert paths.json_path.exists()
    assert paths.markdown_path.exists()
    markdown = paths.markdown_path.read_text(encoding="utf-8")
    assert "Alpha Research Report" in markdown
    assert "Train/Test Split" in markdown
    assert "oos_rank_ic_mean" in paths.json_path.read_text(encoding="utf-8")
