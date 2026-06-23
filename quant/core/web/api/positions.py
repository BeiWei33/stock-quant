"""Positions API router."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import get_paper_db, get_stock_name_map
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()


@router.get("")
async def get_positions(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
):
    """Get current positions."""
    if not conn:
        return ApiResponse(data={"positions": [], "trade_date": None})

    cursor = conn.execute(
        "SELECT MAX(trade_date) FROM positions WHERE account_id = 'paper'"
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return ApiResponse(data={"positions": [], "trade_date": None})

    latest_date = row[0]
    name_map = get_stock_name_map(conn)

    cursor = conn.execute(
        """SELECT ts_code, quantity, weight, market_value, avg_cost
           FROM positions
           WHERE account_id = 'paper' AND trade_date = ? AND quantity > 0
           ORDER BY weight DESC""",
        (latest_date,),
    )

    positions = []
    for row in cursor.fetchall():
        positions.append({
            "ts_code": row[0],
            "name": name_map.get(row[0], "-"),
            "quantity": row[1],
            "weight": row[2],
            "market_value": row[3],
            "avg_cost": row[4],
        })

    return ApiResponse(data={"positions": positions, "trade_date": latest_date})


@router.get("/distribution")
async def get_position_distribution(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
):
    """Get position distribution by industry and individual stock."""
    if not conn:
        return ApiResponse(data={"by_stock": [], "by_industry": []})

    cursor = conn.execute(
        "SELECT MAX(trade_date) FROM positions WHERE account_id = 'paper'"
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return ApiResponse(data={"by_stock": [], "by_industry": []})

    latest_date = row[0]

    # By individual stock
    cursor = conn.execute(
        """SELECT ts_code, weight, market_value
           FROM positions
           WHERE account_id = 'paper' AND trade_date = ? AND quantity > 0
           ORDER BY weight DESC""",
        (latest_date,),
    )

    name_map = get_stock_name_map(conn)
    by_stock = [
        {
            "ts_code": row[0],
            "name": name_map.get(row[0], "-"),
            "weight": row[1],
            "market_value": row[2],
        }
        for row in cursor.fetchall()
    ]

    # By industry (requires joining with stocks table for industry info)
    # This is a placeholder - implement actual industry grouping
    by_industry = []

    return ApiResponse(data={"by_stock": by_stock, "by_industry": by_industry})
