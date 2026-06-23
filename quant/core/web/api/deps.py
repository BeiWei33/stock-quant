"""FastAPI dependencies for database connections and common utilities."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Generator

ROOT = Path(__file__).resolve().parents[4]
PAPER_DB = ROOT / "research_store" / "paper_trading.sqlite3"
MARKET_DB = ROOT / "research_store" / "market_data.sqlite3"
REPORTS_DIR = ROOT / "research_store" / "reports"
MONITORING_DIR = ROOT / "research_store" / "monitoring"


def get_paper_db() -> Generator[sqlite3.Connection, None, None]:
    """Get paper trading database connection."""
    if not PAPER_DB.exists():
        # Return empty connection - API should handle gracefully
        yield None
        return
    conn = sqlite3.connect(str(PAPER_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_market_db() -> Generator[sqlite3.Connection, None, None]:
    """Get market data database connection."""
    if not MARKET_DB.exists():
        yield None
        return
    conn = sqlite3.connect(str(MARKET_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def load_report(name: str) -> dict:
    """Load a JSON report file."""
    path = REPORTS_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


def load_monitoring(name: str) -> dict:
    """Load a monitoring JSON file."""
    path = MONITORING_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


def get_stock_name_map(conn: sqlite3.Connection) -> dict[str, str]:
    """Get stock code to name mapping."""
    try:
        cursor = conn.execute("SELECT ts_code, name FROM stocks")
        return {row["ts_code"]: row["name"] for row in cursor.fetchall()}
    except Exception:
        return {}


def get_latest_trade_date(conn: sqlite3.Connection, table: str = "signal") -> str | None:
    """Get the latest trade date from a table."""
    try:
        cursor = conn.execute(f"SELECT MAX(trade_date) FROM {table}")
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
