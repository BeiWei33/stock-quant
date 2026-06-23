"""Signals API router."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import (
    MARKET_DB,
    get_paper_db,
    get_stock_name_map,
    load_report,
)
from quant.core.web.schemas.common import ApiResponse, PaginatedResponse
from quant.core.web.signal_quality import calculate_signal_quality

router = APIRouter()


@router.get("")
async def get_signals(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    signal_type: str | None = None,
    ts_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Get signal history with pagination and filtering."""
    if not conn:
        return PaginatedResponse(data=[], total=0, page=page, page_size=page_size)

    # Build query
    where_clauses = []
    params = []

    if signal_type:
        where_clauses.append("signal_type = ?")
        params.append(signal_type)
    if ts_code:
        where_clauses.append("ts_code = ?")
        params.append(ts_code)
    if start_date:
        where_clauses.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("trade_date <= ?")
        params.append(end_date)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get total count
    cursor = conn.execute(
        f"SELECT COUNT(*) FROM signal WHERE {where_sql}",
        params,
    )
    total = cursor.fetchone()[0]

    # Get paginated data
    offset = (page - 1) * page_size
    cursor = conn.execute(
        f"""SELECT trade_date, ts_code, strategy_id, signal_type, score, price, reason, target_weight
            FROM signal
            WHERE {where_sql}
            ORDER BY trade_date DESC, score DESC
            LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    )

    # Get stock names
    name_map = {}
    try:
        market_conn = sqlite3.connect(str(MARKET_DB))
        market_conn.row_factory = sqlite3.Row
        name_map = {row["ts_code"]: row["name"] for row in market_conn.execute("SELECT ts_code, name FROM stocks").fetchall()}
        market_conn.close()
    except Exception:
        pass

    signals = []
    for row in cursor.fetchall():
        signals.append({
            "trade_date": row[0],
            "ts_code": row[1],
            "name": name_map.get(row[1], "-"),
            "strategy_id": row[2],
            "signal_type": row[3],
            "score": row[4],
            "price": row[5],
            "reason": row[6],
            "target_weight": row[7],
        })

    return PaginatedResponse(
        data=signals,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
async def get_signal_stats(
    current_user: CurrentUser,
    strategy_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
):
    """Get signal quality statistics."""
    stats = calculate_signal_quality(strategy_id=strategy_id, days=days)

    return ApiResponse(
        data={
            "total_signals": stats.total_signals,
            "buy_signals": stats.buy_signals,
            "sell_signals": stats.sell_signals,
            "win_rate_1d": stats.win_rate_1d,
            "win_rate_5d": stats.win_rate_5d,
            "win_rate_10d": stats.win_rate_10d,
            "avg_return_1d": stats.avg_return_1d,
            "avg_return_5d": stats.avg_return_5d,
            "avg_return_10d": stats.avg_return_10d,
            "best_signal_return": stats.best_signal_return,
            "worst_signal_return": stats.worst_signal_return,
            "sharpe_ratio": stats.sharpe_ratio,
        }
    )


@router.get("/export")
async def export_signals(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
    format: str = Query("csv", regex="^(csv|json)$"),
    signal_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Export signals as CSV or JSON."""
    from fastapi.responses import StreamingResponse, JSONResponse
    import csv
    import io

    if not conn:
        return JSONResponse(content={"error": "Database not available"}, status_code=503)

    # Build query
    where_clauses = []
    params = []
    if signal_type:
        where_clauses.append("signal_type = ?")
        params.append(signal_type)
    if start_date:
        where_clauses.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("trade_date <= ?")
        params.append(end_date)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    cursor = conn.execute(
        f"""SELECT trade_date, ts_code, strategy_id, signal_type, score, price, reason
            FROM signal
            WHERE {where_sql}
            ORDER BY trade_date DESC""",
        params,
    )

    rows = cursor.fetchall()

    if format == "json":
        import json
        data = [
            {
                "trade_date": row[0],
                "ts_code": row[1],
                "strategy_id": row[2],
                "signal_type": row[3],
                "score": row[4],
                "price": row[5],
                "reason": row[6],
            }
            for row in rows
        ]
        return StreamingResponse(
            iter([json.dumps(data, ensure_ascii=False, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=signals.json"},
        )

    # CSV format
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["trade_date", "ts_code", "strategy_id", "signal_type", "score", "price", "reason"])
    for row in rows:
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=signals.csv"},
    )
