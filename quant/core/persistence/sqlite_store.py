from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

from quant.core.models import (
    Event,
    OrderFill,
    OrderIntent,
    OrderRiskResult,
    PortfolioSnapshot,
    StrategyRegistration,
    WorkflowLock,
    WorkflowRun,
)
from quant.core.reconciliation.positions import ReconciliationReport
from quant.core.reconciliation.trades import TradeReconciliationReport


class SqliteStore:
    """Small local store for development and paper-trading audit trails."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS strategy_registry (
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    description TEXT,
                    factor_set_id TEXT,
                    code_hash TEXT,
                    config_hash TEXT,
                    config_json TEXT,
                    research_report_path TEXT,
                    status TEXT DEFAULT 'research',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(strategy_id, strategy_version)
                );

                CREATE TABLE IF NOT EXISTS stocks (
                    ts_code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    exchange TEXT,
                    industry TEXT,
                    list_date TEXT,
                    delist_date TEXT,
                    is_st INTEGER DEFAULT 0,
                    status TEXT,
                    source TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS daily_bar (
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    adj_type TEXT NOT NULL DEFAULT 'none',
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    pre_close REAL,
                    volume INTEGER,
                    amount REAL,
                    source TEXT,
                    quality_flag TEXT DEFAULT 'NORMAL',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(ts_code, trade_date, adj_type)
                );

                CREATE TABLE IF NOT EXISTS benchmark_bar (
                    benchmark_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    source TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(benchmark_code, trade_date)
                );

                CREATE TABLE IF NOT EXISTS signal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL DEFAULT 'v1',
                    factor_set_id TEXT,
                    signal_type TEXT NOT NULL,
                    score REAL,
                    target_weight REAL,
                    reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS universe_snapshot (
                    universe_id TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    include_reason TEXT,
                    exclude_reason TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(universe_id, trade_date, ts_code)
                );

                CREATE TABLE IF NOT EXISTS order_intent (
                    order_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    target_weight REAL NOT NULL,
                    trade_date TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS order_risk_check (
                    order_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    side TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    allowed INTEGER NOT NULL,
                    reasons TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS order_fill (
                    fill_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL,
                    tax REAL NOT NULL,
                    trade_date TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS positions (
                    account_id TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    available_quantity INTEGER NOT NULL,
                    avg_cost REAL,
                    market_value REAL,
                    weight REAL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(account_id, ts_code, trade_date)
                );

                CREATE TABLE IF NOT EXISTS portfolio_snapshot (
                    account_id TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    total_asset REAL,
                    cash REAL,
                    market_value REAL,
                    total_position_ratio REAL,
                    daily_return REAL,
                    cum_return REAL,
                    drawdown REAL,
                    benchmark_code TEXT,
                    excess_return REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(account_id, trade_date)
                );

                CREATE TABLE IF NOT EXISTS reconciliation_report (
                    report_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    local_count INTEGER NOT NULL,
                    broker_count INTEGER NOT NULL,
                    detail TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workflow_run (
                    run_id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    trade_date TEXT,
                    summary_path TEXT,
                    error_msg TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workflow_lock (
                    workflow_name TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS event_log (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    trace_id TEXT,
                    correlation_id TEXT,
                    event_time TEXT NOT NULL,
                    receive_time TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self._ensure_column(conn, "strategy_registry", "config_hash", "TEXT")
            self._ensure_column(conn, "strategy_registry", "config_json", "TEXT")

    def _ensure_column(
        self, conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def save_stocks(self, stocks: pd.DataFrame) -> None:
        if stocks.empty:
            return
        rows = [
            (
                row.ts_code,
                row.name,
                row.exchange,
                row.industry,
                _date_text(row.list_date),
                _date_text(row.delist_date),
                1 if bool(row.is_st) else 0,
                row.status,
                getattr(row, "source", ""),
            )
            for row in stocks.itertuples(index=False)
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO stocks (
                    ts_code, name, exchange, industry, list_date, delist_date,
                    is_st, status, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ts_code) DO UPDATE SET
                    name = excluded.name,
                    exchange = excluded.exchange,
                    industry = excluded.industry,
                    list_date = excluded.list_date,
                    delist_date = excluded.delist_date,
                    is_st = excluded.is_st,
                    status = excluded.status,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def save_daily_bars(self, bars: pd.DataFrame) -> None:
        if bars.empty:
            return
        bars = bars.copy()
        if "pre_close" not in bars.columns:
            bars["pre_close"] = pd.NA
        if "source" not in bars.columns:
            bars["source"] = ""
        if "quality_flag" not in bars.columns:
            bars["quality_flag"] = "NORMAL"
        rows = [
            (
                row.ts_code,
                _date_text(row.trade_date),
                row.adj_type,
                _float_or_none(row.open),
                _float_or_none(row.high),
                _float_or_none(row.low),
                _float_or_none(row.close),
                _float_or_none(row.pre_close),
                _int_or_none(row.volume),
                _float_or_none(row.amount),
                row.source,
                row.quality_flag,
            )
            for row in bars.itertuples(index=False)
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_bar (
                    ts_code, trade_date, adj_type, open, high, low, close, pre_close,
                    volume, amount, source, quality_flag
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ts_code, trade_date, adj_type) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    pre_close = excluded.pre_close,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    source = excluded.source,
                    quality_flag = excluded.quality_flag,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def save_benchmark_bars(self, bars: pd.DataFrame) -> None:
        if bars.empty:
            return
        rows = [
            (
                row.benchmark_code,
                _date_text(row.trade_date),
                _float_or_none(row.open),
                _float_or_none(row.high),
                _float_or_none(row.low),
                _float_or_none(row.close),
                _int_or_none(row.volume),
                row.source,
            )
            for row in bars.itertuples(index=False)
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO benchmark_bar (
                    benchmark_code, trade_date, open, high, low, close, volume, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(benchmark_code, trade_date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    source = excluded.source
                """,
                rows,
            )

    def load_stocks(self) -> pd.DataFrame:
        with self.connect() as conn:
            df = pd.read_sql_query("SELECT * FROM stocks ORDER BY ts_code", conn)
        if df.empty:
            return df
        df["list_date"] = pd.to_datetime(df["list_date"], errors="coerce").dt.date
        df["delist_date"] = pd.to_datetime(df["delist_date"], errors="coerce").dt.date
        df["is_st"] = df["is_st"].astype(bool)
        return df

    def load_daily_bars(
        self,
        start_date: object | None = None,
        end_date: object | None = None,
        adj_type: str | None = None,
    ) -> pd.DataFrame:
        conditions: list[str] = []
        params: list[object] = []
        if start_date is not None:
            conditions.append("trade_date >= ?")
            params.append(_date_text(start_date))
        if end_date is not None:
            conditions.append("trade_date <= ?")
            params.append(_date_text(end_date))
        if adj_type is not None:
            conditions.append("adj_type = ?")
            params.append(adj_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM daily_bar {where} ORDER BY trade_date, ts_code"
        with self.connect() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    def load_benchmark_bars(self, benchmark_code: str | None = None) -> pd.DataFrame:
        params: list[object] = []
        where = ""
        if benchmark_code is not None:
            where = "WHERE benchmark_code = ?"
            params.append(benchmark_code)
        with self.connect() as conn:
            df = pd.read_sql_query(
                f"SELECT * FROM benchmark_bar {where} ORDER BY trade_date, benchmark_code",
                conn,
                params=params,
            )
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    def save_strategy(self, registration: StrategyRegistration) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_registry (
                    strategy_id, strategy_version, description, factor_set_id,
                    code_hash, config_hash, config_json, research_report_path, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(strategy_id, strategy_version) DO UPDATE SET
                    description = excluded.description,
                    factor_set_id = excluded.factor_set_id,
                    code_hash = excluded.code_hash,
                    config_hash = excluded.config_hash,
                    config_json = excluded.config_json,
                    research_report_path = excluded.research_report_path,
                    status = excluded.status
                """,
                (
                    registration.strategy_id,
                    registration.strategy_version,
                    registration.description,
                    registration.factor_set_id,
                    registration.code_hash,
                    registration.config_hash,
                    registration.config_json,
                    registration.research_report_path,
                    registration.status,
                ),
            )

    def load_strategy(self, strategy_id: str, strategy_version: str) -> StrategyRegistration | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT strategy_id, strategy_version, description, factor_set_id,
                       code_hash, config_hash, config_json, research_report_path, status
                FROM strategy_registry
                WHERE strategy_id = ? AND strategy_version = ?
                """,
                (strategy_id, strategy_version),
            ).fetchone()
        if row is None:
            return None
        return StrategyRegistration(
            strategy_id=row["strategy_id"],
            strategy_version=row["strategy_version"],
            description=row["description"] or "",
            factor_set_id=row["factor_set_id"] or "",
            code_hash=row["code_hash"] or "",
            config_hash=row["config_hash"] or "",
            config_json=row["config_json"] or "",
            research_report_path=row["research_report_path"] or "",
            status=row["status"] or "research",
        )

    def list_strategies(self, status: str | None = None) -> list[StrategyRegistration]:
        where = ""
        params: list[str] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT strategy_id, strategy_version, description, factor_set_id,
                       code_hash, config_hash, config_json, research_report_path, status
                FROM strategy_registry
                {where}
                ORDER BY strategy_id, strategy_version
                """,
                params,
            ).fetchall()
        return [
            StrategyRegistration(
                strategy_id=row["strategy_id"],
                strategy_version=row["strategy_version"],
                description=row["description"] or "",
                factor_set_id=row["factor_set_id"] or "",
                code_hash=row["code_hash"] or "",
                config_hash=row["config_hash"] or "",
                config_json=row["config_json"] or "",
                research_report_path=row["research_report_path"] or "",
                status=row["status"] or "research",
            )
            for row in rows
        ]

    def save_signals(self, signals: pd.DataFrame, factor_set_id: str = "") -> None:
        if signals.empty:
            return
        keys = {
            (
                row.trade_date.isoformat() if hasattr(row.trade_date, "isoformat") else str(row.trade_date),
                row.strategy_id,
                row.strategy_version,
            )
            for row in signals[["trade_date", "strategy_id", "strategy_version"]].itertuples(index=False)
        }
        rows = [
            (
                row.trade_date.isoformat() if hasattr(row.trade_date, "isoformat") else str(row.trade_date),
                row.ts_code,
                row.strategy_id,
                row.strategy_version,
                factor_set_id,
                row.signal_type,
                float(row.score),
                float(getattr(row, "target_weight", 0.0)),
                row.reason,
            )
            for row in signals.itertuples(index=False)
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                DELETE FROM signal
                WHERE trade_date = ? AND strategy_id = ? AND strategy_version = ?
                """,
                list(keys),
            )
            conn.executemany(
                """
                INSERT INTO signal (
                    trade_date, ts_code, strategy_id, strategy_version, factor_set_id,
                    signal_type, score, target_weight, reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_universe_snapshot(
        self, universe_id: str, trade_date: object, universe_snapshot: pd.DataFrame
    ) -> None:
        if universe_snapshot.empty:
            return
        trade_date_text = trade_date.isoformat() if hasattr(trade_date, "isoformat") else str(trade_date)
        rows = [
            (
                universe_id,
                trade_date_text,
                row.ts_code,
                row.include_reason,
                row.exclude_reason,
                1 if bool(row.is_active) else 0,
            )
            for row in universe_snapshot.itertuples(index=False)
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO universe_snapshot (
                    universe_id, trade_date, ts_code, include_reason, exclude_reason, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(universe_id, trade_date, ts_code) DO UPDATE SET
                    include_reason = excluded.include_reason,
                    exclude_reason = excluded.exclude_reason,
                    is_active = excluded.is_active
                """,
                rows,
            )

    def save_order_intents(self, intents: Iterable[OrderIntent]) -> None:
        intent_list = list(intents)
        rows = [
            (
                intent.order_id,
                intent.account_id,
                intent.strategy_id,
                intent.ts_code,
                intent.side,
                intent.price,
                intent.quantity,
                intent.target_weight,
                intent.trade_date.isoformat(),
                intent.reason,
                intent.status,
            )
            for intent in intent_list
        ]
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO order_intent (
                    order_id, account_id, strategy_id, ts_code, side, price, quantity,
                    target_weight, trade_date, reason, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET
                    price = excluded.price,
                    quantity = excluded.quantity,
                    target_weight = excluded.target_weight,
                    reason = excluded.reason,
                    status = excluded.status
                """,
                rows,
            )
            _insert_events(
                conn,
                [
                    _event(
                        event_type="OrderIntentEvent",
                        trace_id=intent.order_id,
                        payload=intent.to_dict(),
                    )
                    for intent in intent_list
                ],
            )

    def save_order_risk_results(self, results: Iterable[OrderRiskResult]) -> None:
        result_list = list(results)
        rows = [
            (
                result.order.order_id,
                result.order.account_id,
                result.order.strategy_id,
                result.order.ts_code,
                result.order.side,
                result.order.trade_date.isoformat(),
                1 if result.decision.allowed else 0,
                "; ".join(result.decision.reasons),
            )
            for result in result_list
        ]
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO order_risk_check (
                    order_id, account_id, strategy_id, ts_code, side,
                    trade_date, allowed, reasons
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET
                    allowed = excluded.allowed,
                    reasons = excluded.reasons
                """,
                rows,
            )
            _insert_events(
                conn,
                [
                    _event(
                        event_type="RiskCheckEvent",
                        trace_id=result.order.order_id,
                        payload=result.to_dict(),
                    )
                    for result in result_list
                ],
            )

    def save_order_fills(self, fills: Iterable[OrderFill]) -> None:
        fill_list = list(fills)
        rows = [
            (
                fill.fill_id,
                fill.order_id,
                fill.account_id,
                fill.strategy_id,
                fill.ts_code,
                fill.side,
                fill.price,
                fill.quantity,
                fill.amount,
                fill.fee,
                fill.tax,
                fill.trade_date.isoformat(),
            )
            for fill in fill_list
        ]
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO order_fill (
                    fill_id, order_id, account_id, strategy_id, ts_code, side,
                    price, quantity, amount, fee, tax, trade_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fill_id) DO UPDATE SET
                    price = excluded.price,
                    quantity = excluded.quantity,
                    amount = excluded.amount,
                    fee = excluded.fee,
                    tax = excluded.tax
                """,
                rows,
            )
            conn.executemany(
                "UPDATE order_intent SET status = 'FILLED' WHERE order_id = ?",
                [(fill.order_id,) for fill in fill_list],
            )
            _insert_events(
                conn,
                [
                    _event(
                        event_type="TradeEvent",
                        trace_id=fill.order_id,
                        payload=fill.to_dict(),
                    )
                    for fill in fill_list
                ],
            )

    def save_positions(self, positions: pd.DataFrame) -> None:
        if positions.empty:
            return
        rows = [
            (
                row.account_id,
                row.ts_code,
                _date_text(row.trade_date),
                _int_or_none(row.quantity) or 0,
                _int_or_none(row.available_quantity) or 0,
                _float_or_none(row.avg_cost),
                _float_or_none(row.market_value),
                _float_or_none(row.weight),
            )
            for row in positions.itertuples(index=False)
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO positions (
                    account_id, ts_code, trade_date, quantity, available_quantity,
                    avg_cost, market_value, weight
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, ts_code, trade_date) DO UPDATE SET
                    quantity = excluded.quantity,
                    available_quantity = excluded.available_quantity,
                    avg_cost = excluded.avg_cost,
                    market_value = excluded.market_value,
                    weight = excluded.weight,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def save_portfolio_snapshots(self, snapshots: Iterable[PortfolioSnapshot]) -> None:
        snapshot_list = list(snapshots)
        rows = [
            (
                snapshot.account_id,
                snapshot.trade_date.isoformat(),
                snapshot.total_asset,
                snapshot.cash,
                snapshot.market_value,
                snapshot.total_position_ratio,
                snapshot.daily_return,
                snapshot.cum_return,
                snapshot.drawdown,
                snapshot.excess_return,
            )
            for snapshot in snapshot_list
        ]
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO portfolio_snapshot (
                    account_id, trade_date, total_asset, cash, market_value,
                    total_position_ratio, daily_return, cum_return, drawdown, excess_return
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, trade_date) DO UPDATE SET
                    total_asset = excluded.total_asset,
                    cash = excluded.cash,
                    market_value = excluded.market_value,
                    total_position_ratio = excluded.total_position_ratio,
                    daily_return = excluded.daily_return,
                    cum_return = excluded.cum_return,
                    drawdown = excluded.drawdown,
                    excess_return = excluded.excess_return
                """,
                rows,
            )
            _insert_events(
                conn,
                [
                    _event(
                        event_type="PortfolioSnapshotEvent",
                        trace_id=f"{snapshot.account_id}:{snapshot.trade_date.isoformat()}",
                        payload=snapshot.to_dict(),
                    )
                    for snapshot in snapshot_list
                ],
            )

    def load_latest_positions(self, account_id: str, before_date: object | None = None) -> pd.DataFrame:
        params: list[object] = [account_id]
        where = "account_id = ?"
        if before_date is not None:
            where += " AND trade_date < ?"
            params.append(_date_text(before_date))
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT MAX(trade_date) AS trade_date FROM positions WHERE {where}",
                params,
            ).fetchone()
            latest_date = row["trade_date"] if row is not None else None
            if latest_date is None:
                return pd.DataFrame(
                    columns=[
                        "account_id",
                        "ts_code",
                        "trade_date",
                        "quantity",
                        "available_quantity",
                        "avg_cost",
                        "market_value",
                        "weight",
                    ]
                )
            df = pd.read_sql_query(
                """
                SELECT account_id, ts_code, trade_date, quantity, available_quantity,
                       avg_cost, market_value, weight
                FROM positions
                WHERE account_id = ? AND trade_date = ?
                ORDER BY ts_code
                """,
                conn,
                params=[account_id, latest_date],
            )
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    def load_latest_portfolio_snapshot(
        self, account_id: str, before_date: object | None = None
    ) -> PortfolioSnapshot | None:
        params: list[object] = [account_id]
        where = "account_id = ?"
        if before_date is not None:
            where += " AND trade_date < ?"
            params.append(_date_text(before_date))
        with self.connect() as conn:
            row = conn.execute(
                f"""
                SELECT account_id, trade_date, total_asset, cash, market_value,
                       total_position_ratio, daily_return, cum_return, drawdown,
                       excess_return
                FROM portfolio_snapshot
                WHERE {where}
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        return _portfolio_snapshot_from_row(row)

    def load_portfolio_snapshot(
        self, account_id: str, trade_date: object
    ) -> PortfolioSnapshot | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT account_id, trade_date, total_asset, cash, market_value,
                       total_position_ratio, daily_return, cum_return, drawdown,
                       excess_return
                FROM portfolio_snapshot
                WHERE account_id = ? AND trade_date = ?
                """,
                (account_id, _date_text(trade_date)),
            ).fetchone()
        if row is None:
            return None
        return _portfolio_snapshot_from_row(row)

    def load_order_intents(self, account_id: str, trade_date: object) -> pd.DataFrame:
        with self.connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT order_id, account_id, strategy_id, ts_code, side, price,
                       quantity, target_weight, trade_date, reason, status, created_at
                FROM order_intent
                WHERE account_id = ? AND trade_date = ?
                ORDER BY ts_code, side
                """,
                conn,
                params=[account_id, _date_text(trade_date)],
            )
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    def load_order_fills(self, account_id: str, trade_date: object) -> pd.DataFrame:
        with self.connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT fill_id, order_id, account_id, strategy_id, ts_code, side,
                       price, quantity, amount, fee, tax, trade_date, created_at
                FROM order_fill
                WHERE account_id = ? AND trade_date = ?
                ORDER BY ts_code, side, fill_id
                """,
                conn,
                params=[account_id, _date_text(trade_date)],
            )
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    def load_positions(self, account_id: str, trade_date: object) -> pd.DataFrame:
        with self.connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT account_id, ts_code, trade_date, quantity, available_quantity,
                       avg_cost, market_value, weight
                FROM positions
                WHERE account_id = ? AND trade_date = ?
                ORDER BY weight DESC, ts_code
                """,
                conn,
                params=[account_id, _date_text(trade_date)],
            )
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    def load_order_risk_checks(self, account_id: str, trade_date: object) -> pd.DataFrame:
        with self.connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT order_id, account_id, strategy_id, ts_code, side, trade_date,
                       allowed, reasons, created_at
                FROM order_risk_check
                WHERE account_id = ? AND trade_date = ?
                ORDER BY ts_code, side
                """,
                conn,
                params=[account_id, _date_text(trade_date)],
            )
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["allowed"] = df["allowed"].astype(bool)
        return df

    def load_reconciliation_reports(self, account_id: str, trade_date: object) -> pd.DataFrame:
        with self.connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT report_id, account_id, trade_date, status,
                       local_count, broker_count, detail, created_at
                FROM reconciliation_report
                WHERE account_id = ? AND trade_date = ?
                ORDER BY created_at, report_id
                """,
                conn,
                params=[account_id, _date_text(trade_date)],
            )
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["detail"] = df["detail"].map(_json_loads)
        return df

    def save_events(self, events: Iterable[Event]) -> None:
        event_list = list(events)
        if not event_list:
            return
        with self.connect() as conn:
            _insert_events(conn, event_list)

    def load_events(
        self,
        *,
        event_type: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        conditions: list[str] = []
        params: list[object] = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)
        if correlation_id:
            conditions.append("correlation_id = ?")
            params.append(correlation_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        with self.connect() as conn:
            df = pd.read_sql_query(
                f"""
                SELECT event_id, event_type, source, trace_id, correlation_id,
                       event_time, receive_time, payload, created_at
                FROM event_log
                {where}
                ORDER BY event_time, created_at, event_id
                LIMIT ?
                """,
                conn,
                params=params,
            )
        if df.empty:
            return df
        df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce")
        df["receive_time"] = pd.to_datetime(df["receive_time"], errors="coerce")
        df["payload"] = df["payload"].map(_json_loads)
        return df

    def load_trace(self, trace_id: str, limit: int = 100) -> pd.DataFrame:
        return self.load_events(trace_id=trace_id, limit=limit)

    def save_reconciliation_report(self, report: ReconciliationReport) -> None:
        detail = report.differences.to_json(orient="records", force_ascii=False)
        self._save_reconciliation_row(
            report_id=report.report_id,
            account_id=report.account_id,
            trade_date=report.trade_date,
            status=report.status,
            local_count=report.local_count,
            broker_count=report.broker_count,
            detail=detail,
        )

    def save_trade_reconciliation_report(self, report: TradeReconciliationReport) -> None:
        self._save_reconciliation_row(
            report_id=report.report_id,
            account_id=report.account_id,
            trade_date=report.trade_date,
            status=report.status,
            local_count=report.local_count,
            broker_count=report.broker_count,
            detail=json.dumps(report.to_dict(), ensure_ascii=False),
        )

    def _save_reconciliation_row(
        self,
        *,
        report_id: str,
        account_id: str,
        trade_date: object,
        status: str,
        local_count: int,
        broker_count: int,
        detail: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reconciliation_report (
                    report_id, account_id, trade_date, status,
                    local_count, broker_count, detail
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    status = excluded.status,
                    local_count = excluded.local_count,
                    broker_count = excluded.broker_count,
                    detail = excluded.detail
                """,
                (
                    report_id,
                    account_id,
                    _date_text(trade_date),
                    status,
                    local_count,
                    broker_count,
                    detail,
                ),
            )

    def save_workflow_run(self, run: WorkflowRun) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO workflow_run (
                    run_id, workflow_name, status, started_at, ended_at,
                    trade_date, summary_path, error_msg
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    ended_at = excluded.ended_at,
                    trade_date = excluded.trade_date,
                    summary_path = excluded.summary_path,
                    error_msg = excluded.error_msg
                """,
                (
                    run.run_id,
                    run.workflow_name,
                    run.status,
                    run.started_at.isoformat(),
                    run.ended_at.isoformat() if run.ended_at else None,
                    run.trade_date.isoformat() if run.trade_date else None,
                    run.summary_path,
                    run.error_msg,
                ),
            )

    def load_latest_workflow_run(self, workflow_name: str | None = None) -> WorkflowRun | None:
        params: list[object] = []
        where = ""
        if workflow_name:
            where = "WHERE workflow_name = ?"
            params.append(workflow_name)
        with self.connect() as conn:
            row = conn.execute(
                f"""
                SELECT run_id, workflow_name, status, started_at, ended_at,
                       trade_date, summary_path, error_msg
                FROM workflow_run
                {where}
                ORDER BY started_at DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        return WorkflowRun(
            run_id=row["run_id"],
            workflow_name=row["workflow_name"],
            status=row["status"],
            started_at=pd.to_datetime(row["started_at"]).to_pydatetime(),
            ended_at=pd.to_datetime(row["ended_at"]).to_pydatetime() if row["ended_at"] else None,
            trade_date=pd.to_datetime(row["trade_date"]).date() if row["trade_date"] else None,
            summary_path=row["summary_path"] or "",
            error_msg=row["error_msg"] or "",
        )

    def acquire_workflow_lock(self, lock: WorkflowLock) -> bool:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM workflow_lock WHERE workflow_name = ? AND expires_at <= ?",
                (lock.workflow_name, lock.acquired_at.isoformat()),
            )
            try:
                conn.execute(
                    """
                    INSERT INTO workflow_lock (
                        workflow_name, run_id, acquired_at, expires_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        lock.workflow_name,
                        lock.run_id,
                        lock.acquired_at.isoformat(),
                        lock.expires_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def release_workflow_lock(self, workflow_name: str, run_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM workflow_lock WHERE workflow_name = ? AND run_id = ?",
                (workflow_name, run_id),
            )

    def load_workflow_lock(self, workflow_name: str) -> WorkflowLock | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT workflow_name, run_id, acquired_at, expires_at
                FROM workflow_lock
                WHERE workflow_name = ?
                """,
                (workflow_name,),
            ).fetchone()
        if row is None:
            return None
        return WorkflowLock(
            workflow_name=row["workflow_name"],
            run_id=row["run_id"],
            acquired_at=pd.to_datetime(row["acquired_at"]).to_pydatetime(),
            expires_at=pd.to_datetime(row["expires_at"]).to_pydatetime(),
        )

    def count_rows(self, table: str) -> int:
        if not table.replace("_", "").isalnum():
            raise ValueError("invalid table name")
        with self.connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            return int(row["count"])


def _portfolio_snapshot_from_row(row: sqlite3.Row) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        account_id=row["account_id"],
        trade_date=pd.to_datetime(row["trade_date"]).date(),
        total_asset=float(row["total_asset"] or 0.0),
        cash=float(row["cash"] or 0.0),
        market_value=float(row["market_value"] or 0.0),
        total_position_ratio=float(row["total_position_ratio"] or 0.0),
        daily_return=float(row["daily_return"] or 0.0),
        cum_return=float(row["cum_return"] or 0.0),
        drawdown=float(row["drawdown"] or 0.0),
        excess_return=float(row["excess_return"] or 0.0),
    )


def _date_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _float_or_none(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _int_or_none(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _event(event_type: str, trace_id: str, payload: dict[str, object]) -> Event:
    return Event(
        event_type=event_type,
        source="sqlite_store",
        trace_id=trace_id,
        correlation_id=str(payload.get("trade_date", "")),
        payload=payload,
    )


def _insert_events(conn: sqlite3.Connection, events: Iterable[Event]) -> None:
    rows = [
        (
            event.event_id,
            event.event_type,
            event.source,
            event.trace_id,
            event.correlation_id,
            event.event_time.isoformat(),
            event.receive_time.isoformat(),
            json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
        )
        for event in events
    ]
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO event_log (
            event_id, event_type, source, trace_id, correlation_id,
            event_time, receive_time, payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            event_type = excluded.event_type,
            source = excluded.source,
            trace_id = excluded.trace_id,
            correlation_id = excluded.correlation_id,
            event_time = excluded.event_time,
            receive_time = excluded.receive_time,
            payload = excluded.payload
        """,
        rows,
    )


def _json_loads(value: object) -> object:
    if value is None or pd.isna(value):
        return {}
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return {}
