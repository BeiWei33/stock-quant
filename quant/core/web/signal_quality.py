"""Signal quality analysis service."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAPER_DB = ROOT / "research_store" / "paper_trading.sqlite3"
MARKET_DB = ROOT / "research_store" / "market_data.sqlite3"


@dataclass
class SignalQualityStats:
    """Signal quality statistics."""
    total_signals: int
    buy_signals: int
    sell_signals: int
    win_rate_1d: float | None = None
    win_rate_5d: float | None = None
    win_rate_10d: float | None = None
    avg_return_1d: float | None = None
    avg_return_5d: float | None = None
    avg_return_10d: float | None = None
    best_signal_return: float | None = None
    worst_signal_return: float | None = None
    sharpe_ratio: float | None = None


def calculate_signal_quality(
    strategy_id: str | None = None,
    days: int = 30,
) -> SignalQualityStats:
    """Calculate signal quality statistics."""
    if not PAPER_DB.exists():
        return SignalQualityStats(total_signals=0, buy_signals=0, sell_signals=0)

    conn = sqlite3.connect(str(PAPER_DB))
    conn.row_factory = sqlite3.Row

    # Get date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Build query
    where_clauses = ["trade_date >= ?"]
    params = [start_date.strftime("%Y-%m-%d")]

    if strategy_id:
        where_clauses.append("strategy_id = ?")
        params.append(strategy_id)

    where_sql = " AND ".join(where_clauses)

    # Get signals
    cursor = conn.execute(
        f"""SELECT trade_date, ts_code, signal_type, score, price
            FROM signal
            WHERE {where_sql}
            ORDER BY trade_date""",
        params,
    )

    signals = cursor.fetchall()

    if not signals:
        conn.close()
        return SignalQualityStats(total_signals=0, buy_signals=0, sell_signals=0)

    # Get market data for return calculation
    market_conn = sqlite3.connect(str(MARKET_DB))
    market_conn.row_factory = sqlite3.Row

    buy_count = 0
    sell_count = 0
    returns_1d = []
    returns_5d = []
    returns_10d = []

    for signal in signals:
        trade_date = signal["trade_date"]
        ts_code = signal["ts_code"]
        signal_type = signal["signal_type"]
        price = signal["price"]

        if signal_type == "BUY":
            buy_count += 1
        else:
            sell_count += 1

        if not price:
            continue

        # Calculate returns after signal
        for days_after, returns_list in [(1, returns_1d), (5, returns_5d), (10, returns_10d)]:
            future_date = _get_future_trade_date(market_conn, trade_date, days_after)
            if not future_date:
                continue

            cursor = market_conn.execute(
                "SELECT close FROM daily_bar WHERE ts_code = ? AND trade_date = ?",
                (ts_code, future_date),
            )
            row = cursor.fetchone()
            if row and row["close"]:
                future_price = row["close"]
                ret = (future_price - price) / price
                returns_list.append(ret)

    market_conn.close()
    conn.close()

    # Calculate statistics
    import numpy as np

    def calc_win_rate(returns: list[float]) -> float | None:
        if not returns:
            return None
        wins = sum(1 for r in returns if r > 0)
        return wins / len(returns)

    def calc_avg_return(returns: list[float]) -> float | None:
        if not returns:
            return None
        return float(np.mean(returns))

    def calc_sharpe(returns: list[float]) -> float | None:
        if len(returns) < 2:
            return None
        mean = np.mean(returns)
        std = np.std(returns)
        if std == 0:
            return None
        return float(mean / std * np.sqrt(252))  # Annualized

    all_returns = returns_1d + returns_5d + returns_10d

    return SignalQualityStats(
        total_signals=len(signals),
        buy_signals=buy_count,
        sell_signals=sell_count,
        win_rate_1d=calc_win_rate(returns_1d),
        win_rate_5d=calc_win_rate(returns_5d),
        win_rate_10d=calc_win_rate(returns_10d),
        avg_return_1d=calc_avg_return(returns_1d),
        avg_return_5d=calc_avg_return(returns_5d),
        avg_return_10d=calc_avg_return(returns_10d),
        best_signal_return=max(all_returns) if all_returns else None,
        worst_signal_return=min(all_returns) if all_returns else None,
        sharpe_ratio=calc_sharpe(returns_1d),
    )


def _get_future_trade_date(conn: sqlite3.Connection, start_date: str, days: int) -> str | None:
    """Get the trade date N days after start_date."""
    cursor = conn.execute(
        """SELECT DISTINCT trade_date
           FROM daily_bar
           WHERE trade_date > ?
           ORDER BY trade_date
           LIMIT 1 OFFSET ?""",
        (start_date, days - 1),
    )
    row = cursor.fetchone()
    return row["trade_date"] if row else None
