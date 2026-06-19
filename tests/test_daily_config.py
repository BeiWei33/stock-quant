from __future__ import annotations

from pathlib import Path

from quant.core.config.daily import DailyAppConfig


def test_daily_config_loads_yaml_and_generates_args(tmp_path) -> None:
    config_path = tmp_path / "daily.yaml"
    config_path.write_text(
        """
source:
  type: csv
  stocks: data/stocks.csv
  bars: data/bars.csv
  akshare_symbols: 600519.SH,000001.SZ
  akshare_limit: 12
storage:
  market_sqlite: data/market.sqlite3
  paper_sqlite: data/paper.sqlite3
  report_dir: reports
  output: reports/summary.json
workflow:
  account_id: paper
  strategy: quality_rank
  factor: momentum_20d
  horizon: 3
  quantiles: 4
  initial_cash: 500000
  apply_fills: false
quality:
  enabled: false
  fail_on_error: true
  check_weekday_gaps: false
run:
  use_lock: false
  lock_ttl_minutes: 15
""",
        encoding="utf-8",
    )

    config = DailyAppConfig.from_file(config_path)
    args = config.daily_args()

    assert config.factor == "momentum_20d"
    assert config.strategy == "quality_rank"
    assert config.initial_cash == 500000
    assert not config.apply_fills
    assert not config.quality_check_enabled
    assert config.fail_on_quality_error
    assert not config.quality_check_weekday_gaps
    assert not config.use_lock
    assert "--stocks data/stocks.csv" in args
    assert "--akshare-symbols 600519.SH,000001.SZ" in args
    assert "--akshare-limit 12" in args
    assert "--strategy quality_rank" in args
    assert "--no-apply-fills" in args
    assert "--no-quality-check" in args
    assert "--fail-on-quality-error" in args
    assert "--no-quality-weekday-gaps" in args
    assert "--no-lock" in args


def test_daily_config_cli_merge_overrides_values() -> None:
    config = DailyAppConfig.from_dict({"workflow": {"factor": "momentum_20d"}})

    merged = config.merge_cli({"strategy": "quality_rank", "factor": "momentum_60d", "horizon": 10, "stocks": None})

    assert merged.strategy == "quality_rank"
    assert merged.factor == "momentum_60d"
    assert merged.horizon == 10
    assert merged.stocks is None
