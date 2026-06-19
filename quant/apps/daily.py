from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pandas as pd

from quant.core.collector.akshare_source import (
    DEFAULT_A_SHARE_SYMBOLS,
    AkShareDataSource,
    AkShareDataSourceConfig,
)
from quant.core.collector.base import MarketDataSource
from quant.core.collector.csv_source import CsvDataSource, CsvDataSourceConfig
from quant.core.collector.tushare_source import TushareDataSource
from quant.core.config.daily import DailyAppConfig
from quant.core.models import WorkflowLock, WorkflowRun
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.workflow.daily import DailyWorkflow, DailyWorkflowConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the daily paper-trading workflow.")
    parser.add_argument("--config")
    parser.add_argument("--source", choices=["csv", "akshare", "tushare"])
    parser.add_argument("--stocks")
    parser.add_argument("--bars")
    parser.add_argument("--benchmark-bars")
    parser.add_argument("--benchmark-code")
    parser.add_argument(
        "--akshare-symbols",
        help="Comma-separated A-share symbols for AkShare, e.g. 600519.SH,000001.SZ.",
    )
    parser.add_argument("--akshare-symbols-file", help="Text file with one AkShare symbol per line.")
    parser.add_argument("--akshare-limit", type=int, help="Limit AkShare collection to the first N symbols.")
    parser.add_argument("--akshare-all", action="store_true", default=None, help="Collect the full AkShare A-share universe.")
    parser.add_argument("--tushare-token")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--trade-date")
    parser.add_argument("--market-sqlite")
    parser.add_argument("--paper-sqlite")
    parser.add_argument("--report-dir")
    parser.add_argument("--output")
    parser.add_argument("--account-id")
    parser.add_argument("--strategy")
    parser.add_argument("--factor")
    parser.add_argument("--horizon", type=int)
    parser.add_argument("--quantiles", type=int)
    parser.add_argument("--initial-cash", type=float)
    parser.add_argument("--apply-fills", action="store_true", default=None)
    parser.add_argument("--no-apply-fills", action="store_true", default=None)
    parser.add_argument("--quality-check", action="store_true", default=None)
    parser.add_argument("--no-quality-check", action="store_true", default=None)
    parser.add_argument("--fail-on-quality-error", action="store_true", default=None)
    parser.add_argument("--no-fail-on-quality-error", action="store_true", default=None)
    parser.add_argument("--quality-weekday-gaps", action="store_true", default=None)
    parser.add_argument("--no-quality-weekday-gaps", action="store_true", default=None)
    parser.add_argument("--use-lock", action="store_true", default=None)
    parser.add_argument("--no-lock", action="store_true", default=None)
    parser.add_argument("--lock-ttl-minutes", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = _resolve_config(args)
    run_id = uuid4().hex
    started_at = datetime.now(UTC)
    output = Path(config.output)
    run_store = SqliteStore(Path(config.paper_sqlite))
    run_store.init_schema()
    lock_acquired = False
    if config.use_lock:
        lock = WorkflowLock(
            workflow_name="daily",
            run_id=run_id,
            acquired_at=started_at,
            expires_at=started_at + timedelta(minutes=config.lock_ttl_minutes),
        )
        lock_acquired = run_store.acquire_workflow_lock(lock)
        if not lock_acquired:
            error_msg = "daily workflow is already running"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "run_status": "FAILED",
                        "error_msg": error_msg,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            run_store.save_workflow_run(
                WorkflowRun(
                    run_id=run_id,
                    workflow_name="daily",
                    status="FAILED",
                    started_at=started_at,
                    ended_at=datetime.now(UTC),
                    summary_path=str(output),
                    error_msg=error_msg,
                )
            )
            raise RuntimeError(error_msg)
    run_store.save_workflow_run(
        WorkflowRun(
            run_id=run_id,
            workflow_name="daily",
            status="RUNNING",
            started_at=started_at,
            summary_path=str(output),
        )
    )
    workflow = DailyWorkflow(
        DailyWorkflowConfig(
            market_store_path=Path(config.market_sqlite),
            paper_store_path=Path(config.paper_sqlite),
            report_dir=Path(config.report_dir),
            account_id=config.account_id,
            strategy_name=config.strategy,
            factor_name=config.factor,
            horizon=config.horizon,
            quantiles=config.quantiles,
            initial_cash=config.initial_cash,
            apply_fills=config.apply_fills,
            quality_check_enabled=config.quality_check_enabled,
            fail_on_quality_error=config.fail_on_quality_error,
            quality_check_weekday_gaps=config.quality_check_weekday_gaps,
        )
    )
    try:
        result = workflow.run(
            source=_build_source(config),
            start_date=_parse_date(config.start_date),
            end_date=_parse_date(config.end_date),
            trade_date=_parse_date(config.trade_date),
        )
        status = "SUCCESS" if result.ok else "CHECK"
        payload = result.to_dict()
        payload["run_id"] = run_id
        payload["run_status"] = status
        payload["data_source"] = config.source
        payload["market_data_mode"] = _market_data_mode(config)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        run_store.save_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_name="daily",
                status=status,
                started_at=started_at,
                ended_at=datetime.now(UTC),
                trade_date=result.trade_date,
                summary_path=str(output),
            )
        )
        print(f"Wrote daily workflow summary to {output}")
        print(f"Daily workflow status: {status}")
    except Exception as exc:
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "run_status": "FAILED",
            "error_msg": str(exc),
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        run_store.save_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_name="daily",
                status="FAILED",
                started_at=started_at,
                ended_at=datetime.now(UTC),
                summary_path=str(output),
                error_msg=str(exc),
            )
        )
        raise
    finally:
        if lock_acquired:
            run_store.release_workflow_lock("daily", run_id)


def _resolve_config(args: argparse.Namespace) -> DailyAppConfig:
    config = DailyAppConfig.from_file(Path(args.config)) if args.config else DailyAppConfig()
    overrides = {
        "source": args.source,
        "stocks": args.stocks,
        "bars": args.bars,
        "benchmark_bars": args.benchmark_bars,
        "benchmark_code": args.benchmark_code,
        "akshare_symbols": args.akshare_symbols,
        "akshare_symbols_file": args.akshare_symbols_file,
        "akshare_limit": args.akshare_limit,
        "akshare_all_market": _bool_override(args.akshare_all, None),
        "tushare_token": args.tushare_token,
        "start_date": args.start_date or (datetime.now(UTC).date() - timedelta(days=260)).isoformat(),
        "end_date": args.end_date or datetime.now(UTC).date().isoformat(),
        "trade_date": args.trade_date,
        "market_sqlite": args.market_sqlite,
        "paper_sqlite": args.paper_sqlite,
        "report_dir": args.report_dir,
        "output": args.output,
        "account_id": args.account_id,
        "strategy": args.strategy,
        "factor": args.factor,
        "horizon": args.horizon,
        "quantiles": args.quantiles,
        "initial_cash": args.initial_cash,
        "apply_fills": _bool_override(args.apply_fills, args.no_apply_fills),
        "quality_check_enabled": _bool_override(args.quality_check, args.no_quality_check),
        "fail_on_quality_error": _bool_override(
            args.fail_on_quality_error, args.no_fail_on_quality_error
        ),
        "quality_check_weekday_gaps": _bool_override(
            args.quality_weekday_gaps, args.no_quality_weekday_gaps
        ),
        "use_lock": _bool_override(args.use_lock, args.no_lock),
        "lock_ttl_minutes": args.lock_ttl_minutes,
    }
    return config.merge_cli(overrides)



def _bool_override(enabled: bool | None, disabled: bool | None) -> bool | None:
    if enabled:
        return True
    if disabled:
        return False
    return None


def _build_source(config: DailyAppConfig) -> MarketDataSource:
    if config.source == "csv":
        if not config.stocks or not config.bars:
            raise ValueError("--stocks and --bars are required for csv daily workflow")
        return CsvDataSource(
            CsvDataSourceConfig(
                stocks_path=Path(config.stocks),
                daily_bars_path=Path(config.bars),
                benchmark_bars_path=Path(config.benchmark_bars) if config.benchmark_bars else None,
                benchmark_code=config.benchmark_code,
            )
        )
    if config.source == "akshare":
        return AkShareDataSource(
            AkShareDataSourceConfig(
                symbols=_akshare_symbols(config) or DEFAULT_A_SHARE_SYMBOLS,
                max_symbols=config.akshare_limit,
                all_market=config.akshare_all_market,
            )
        )
    if config.source == "tushare":
        return TushareDataSource(token=config.tushare_token or "")
    raise ValueError(f"unsupported source: {config.source}")


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return pd.to_datetime(value).date()


def _akshare_symbols(config: DailyAppConfig) -> tuple[str, ...]:
    symbols: list[str] = []
    if config.akshare_symbols_file:
        path = Path(config.akshare_symbols_file)
        symbols.extend(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    if config.akshare_symbols:
        symbols.extend(part.strip() for part in config.akshare_symbols.split(",") if part.strip())
    return tuple(symbols)


def _market_data_mode(config: DailyAppConfig) -> dict[str, object]:
    if config.source == "akshare":
        return {
            "source": "akshare",
            "label": "AkShare 真实 A 股行情",
            "tradable": False,
            "note": "通过 AkShare 获取公开 A 股行情数据，仅用于研究和模拟盘，不代表已经接入实盘交易。",
            "symbols": list(_akshare_symbols(config) or DEFAULT_A_SHARE_SYMBOLS),
            "limit": config.akshare_limit,
            "all_market": config.akshare_all_market,
        }
    if config.source == "tushare":
        return {
            "source": "tushare",
            "label": "Tushare 行情数据",
            "tradable": False,
            "note": "通过 Tushare 获取行情数据，仅用于研究和模拟盘，不代表已经接入实盘交易。",
        }
    return {
        "source": "csv",
        "label": "本地样例/CSV 数据",
        "tradable": False,
        "note": "默认本地流程使用样例或 CSV 数据；请不要当成真实可交易行情。",
    }


if __name__ == "__main__":
    main()
