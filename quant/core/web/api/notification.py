"""Notification API router."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import MARKET_DB, get_paper_db, get_stock_name_map
from quant.core.web.notification import notifier
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()


@router.post("/send")
async def send_notification(
    current_user: CurrentUser,
    conn: sqlite3.Connection = Depends(get_paper_db),
):
    """Manually trigger signal notification for today's signals."""
    # Get latest signals
    cursor = conn.execute("SELECT MAX(trade_date) FROM signal")
    row = cursor.fetchone()
    if not row or not row[0]:
        return ApiResponse(code=404, message="No signals found")

    trade_date = row[0]

    # Get stock names
    name_map = get_stock_name_map(conn)

    # Get signals
    cursor = conn.execute(
        """SELECT ts_code, signal_type, score, price, reason
           FROM signal
           WHERE trade_date = ?
           ORDER BY score DESC""",
        (trade_date,),
    )

    signals = [
        {
            "ts_code": row[0],
            "name": name_map.get(row[0], row[0]),
            "signal_type": row[1],
            "score": row[2],
            "price": row[3],
            "reason": row[4],
        }
        for row in cursor.fetchall()
    ]

    if not signals:
        return ApiResponse(code=404, message="No signals found for today")

    # Send notifications
    import asyncio
    results = await notifier.notify_signals(signals, trade_date)

    return ApiResponse(
        data={
            "trade_date": trade_date,
            "signal_count": len(signals),
            "results": results,
        }
    )


@router.get("/config")
async def get_notification_config(current_user: CurrentUser):
    """Get notification configuration."""
    config = notifier.config
    return ApiResponse(
        data={
            "enabled": config.enabled,
            "dingtalk_configured": bool(config.dingtalk_webhook),
            "wechat_configured": bool(config.wechat_webhook),
            "notify_on_buy": config.notify_on_buy,
            "notify_on_sell": config.notify_on_sell,
            "min_score": config.min_score,
        }
    )
