"""Market data API router for K-line charts."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import MARKET_DB, get_market_db, get_paper_db
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()


@router.get("/stocks")
async def get_stock_list(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_market_db),
    keyword: str = Query("", description="Search keyword"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get stock list for search."""
    if not conn:
        return ApiResponse(data=[])

    if keyword:
        cursor = conn.execute(
            """SELECT ts_code, name, exchange, industry
               FROM stocks
               WHERE ts_code LIKE ? OR name LIKE ?
               LIMIT ?""",
            (f"%{keyword}%", f"%{keyword}%", limit),
        )
    else:
        cursor = conn.execute(
            """SELECT ts_code, name, exchange, industry
               FROM stocks
               LIMIT ?""",
            (limit,),
        )

    stocks = [
        {
            "ts_code": row[0],
            "name": row[1],
            "exchange": row[2],
            "industry": row[3],
        }
        for row in cursor.fetchall()
    ]

    return ApiResponse(data=stocks)


@router.get("/kline")
async def get_kline_data(
    current_user: CurrentUser,
    ts_code: str = Query(..., description="Stock code"),
    period: str = Query("daily", description="Period: daily/weekly/monthly"),
    limit: int = Query(250, ge=1, le=2000),
    conn: sqlite3.Connection | None = Depends(get_market_db),
):
    """Get K-line data for a stock."""
    if not conn:
        return ApiResponse(data=None, message="Database not available")

    # Query daily bar data
    cursor = conn.execute(
        """SELECT trade_date, open, high, low, close, volume, amount
           FROM daily_bar
           WHERE ts_code = ?
           ORDER BY trade_date DESC
           LIMIT ?""",
        (ts_code, limit),
    )

    rows = cursor.fetchall()

    # Format for ECharts candlestick
    kline_data = []
    volume_data = []
    dates = []

    for row in reversed(rows):  # Reverse to chronological order
        dates.append(row[0])
        kline_data.append([row[1], row[4], row[3], row[2]])  # [open, close, low, high]
        volume_data.append(row[5])

    # Get stock info
    cursor = conn.execute(
        "SELECT name FROM stocks WHERE ts_code = ?",
        (ts_code,),
    )
    stock_info = cursor.fetchone()
    stock_name = stock_info[0] if stock_info else ts_code

    # Calculate moving averages
    closes = [row[4] for row in reversed(rows)]
    ma5 = _calculate_ma(closes, 5)
    ma10 = _calculate_ma(closes, 10)
    ma20 = _calculate_ma(closes, 20)
    ma60 = _calculate_ma(closes, 60)

    return ApiResponse(
        data={
            "ts_code": ts_code,
            "name": stock_name,
            "dates": dates,
            "kline": kline_data,
            "volume": volume_data,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
        }
    )


@router.get("/signals/{ts_code}")
async def get_stock_signals(
    ts_code: str,
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
    limit: int = Query(100, ge=1, le=500),
):
    """Get signal markers for a stock."""
    if not conn:
        return ApiResponse(data=[])

    cursor = conn.execute(
        """SELECT trade_date, signal_type, score, price
           FROM signal
           WHERE ts_code = ?
           ORDER BY trade_date DESC
           LIMIT ?""",
        (ts_code, limit),
    )

    signals = [
        {
            "trade_date": row[0],
            "signal_type": row[1],
            "score": row[2],
            "price": row[3],
        }
        for row in cursor.fetchall()
    ]

    return ApiResponse(data=signals)


def _calculate_ma(data: list[float], period: int) -> list[float | None]:
    """Calculate moving average."""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            avg = sum(data[i - period + 1 : i + 1]) / period
            result.append(round(avg, 2))
    return result
