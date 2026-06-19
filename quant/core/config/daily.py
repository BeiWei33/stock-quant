from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DailyAppConfig:
    source: str = "csv"
    stocks: str | None = None
    bars: str | None = None
    benchmark_bars: str | None = None
    benchmark_code: str = "equal_weight"
    akshare_symbols: str | None = None
    akshare_symbols_file: str | None = None
    akshare_limit: int | None = None
    akshare_all_market: bool = False
    tushare_token: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    trade_date: str | None = None
    market_sqlite: str = "research_store/market_data.sqlite3"
    paper_sqlite: str = "research_store/paper_trading.sqlite3"
    report_dir: str = "research_store/reports"
    output: str = "research_store/reports/daily_summary.json"
    account_id: str = "paper"
    strategy: str = "momentum_rank"
    factor: str = "momentum_60d"
    horizon: int = 5
    quantiles: int = 5
    initial_cash: float = 1_000_000
    price_min: float | None = None
    price_max: float | None = None
    apply_fills: bool = True
    quality_check_enabled: bool = True
    fail_on_quality_error: bool = False
    quality_check_weekday_gaps: bool = True
    use_lock: bool = True
    lock_ttl_minutes: int = 120

    @classmethod
    def from_file(cls, path: Path) -> "DailyAppConfig":
        if not path.exists():
            raise FileNotFoundError(f"daily config not found: {path}")
        payload = _load_config_file(path)
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DailyAppConfig":
        source = payload.get("source", {})
        storage = payload.get("storage", {})
        workflow = payload.get("workflow", {})
        quality = payload.get("quality", {})
        run = payload.get("run", {})
        return cls(
            source=str(source.get("type", "csv")),
            stocks=source.get("stocks"),
            bars=source.get("bars"),
            benchmark_bars=source.get("benchmark_bars"),
            benchmark_code=str(source.get("benchmark_code", "equal_weight")),
            akshare_symbols=source.get("akshare_symbols"),
            akshare_symbols_file=source.get("akshare_symbols_file"),
            akshare_limit=(
                int(source["akshare_limit"]) if source.get("akshare_limit") is not None else None
            ),
            akshare_all_market=bool(source.get("akshare_all_market", False)),
            tushare_token=source.get("tushare_token"),
            start_date=source.get("start_date"),
            end_date=source.get("end_date"),
            trade_date=source.get("trade_date"),
            market_sqlite=str(storage.get("market_sqlite", "research_store/market_data.sqlite3")),
            paper_sqlite=str(storage.get("paper_sqlite", "research_store/paper_trading.sqlite3")),
            report_dir=str(storage.get("report_dir", "research_store/reports")),
            output=str(storage.get("output", "research_store/reports/daily_summary.json")),
            account_id=str(workflow.get("account_id", "paper")),
            strategy=str(workflow.get("strategy", "momentum_rank")),
            factor=str(workflow.get("factor", "momentum_60d")),
            horizon=int(workflow.get("horizon", 5)),
            quantiles=int(workflow.get("quantiles", 5)),
            initial_cash=float(workflow.get("initial_cash", 1_000_000)),
            apply_fills=bool(workflow.get("apply_fills", True)),
            quality_check_enabled=bool(quality.get("enabled", True)),
            fail_on_quality_error=bool(quality.get("fail_on_error", False)),
            quality_check_weekday_gaps=bool(quality.get("check_weekday_gaps", True)),
            use_lock=bool(run.get("use_lock", True)),
            lock_ttl_minutes=int(run.get("lock_ttl_minutes", 120)),
        )

    def merge_cli(self, overrides: dict[str, Any]) -> "DailyAppConfig":
        values = self.__dict__.copy()
        for key, value in overrides.items():
            if value is not None:
                values[key] = value
        return DailyAppConfig(**values)

    def daily_args(self) -> str:
        parts = [
            f"--source {self.source}",
            f"--market-sqlite {self.market_sqlite}",
            f"--paper-sqlite {self.paper_sqlite}",
            f"--report-dir {self.report_dir}",
            f"--output {self.output}",
            f"--account-id {self.account_id}",
            f"--strategy {self.strategy}",
            f"--factor {self.factor}",
            f"--horizon {self.horizon}",
            f"--quantiles {self.quantiles}",
            f"--initial-cash {self.initial_cash:g}",
            f"--lock-ttl-minutes {self.lock_ttl_minutes}",
        ]
        if self.stocks:
            parts.append(f"--stocks {self.stocks}")
        if self.bars:
            parts.append(f"--bars {self.bars}")
        if self.benchmark_bars:
            parts.append(f"--benchmark-bars {self.benchmark_bars}")
        if self.benchmark_code:
            parts.append(f"--benchmark-code {self.benchmark_code}")
        if self.akshare_symbols:
            parts.append(f"--akshare-symbols {self.akshare_symbols}")
        if self.akshare_symbols_file:
            parts.append(f"--akshare-symbols-file {self.akshare_symbols_file}")
        if self.akshare_limit is not None:
            parts.append(f"--akshare-limit {self.akshare_limit}")
        if self.akshare_all_market:
            parts.append("--akshare-all")
        if self.tushare_token:
            parts.append(f"--tushare-token {self.tushare_token}")
        if self.start_date:
            parts.append(f"--start-date {self.start_date}")
        if self.end_date:
            parts.append(f"--end-date {self.end_date}")
        if self.trade_date:
            parts.append(f"--trade-date {self.trade_date}")
        if not self.apply_fills:
            parts.append("--no-apply-fills")
        if self.quality_check_enabled:
            parts.append("--quality-check")
        else:
            parts.append("--no-quality-check")
        if self.fail_on_quality_error:
            parts.append("--fail-on-quality-error")
        else:
            parts.append("--no-fail-on-quality-error")
        if not self.quality_check_weekday_gaps:
            parts.append("--no-quality-weekday-gaps")
        if not self.use_lock:
            parts.append("--no-lock")
        return " ".join(parts)


def _load_config_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read YAML config files") from exc
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("daily config must be a mapping")
    return data
