"""Dashboard API router."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import (
    get_latest_trade_date,
    get_paper_db,
    get_stock_name_map,
    load_monitoring,
    load_report,
)
from quant.core.web.schemas.common import ApiResponse, StatusCard

router = APIRouter()


@router.get("/overview")
async def get_dashboard_overview(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
):
    """Get dashboard overview: system status + account metrics."""
    # Load system status from reports
    daily_summary = load_report("daily_summary.json")
    readiness = load_monitoring("readiness.json")
    config_health = load_monitoring("config_health.json")
    alerts = load_monitoring("alerts.json")

    # System status cards
    run_status = daily_summary.get("run_status", "N/A")
    paper_ready = readiness.get("paper_ready", False)
    config_status = config_health.get("status", "N/A")
    alert_status = alerts.get("status", "OK")

    status_cards = [
        StatusCard(
            label="运行状态",
            value=run_status,
            status="ok" if run_status == "SUCCESS" else "warning",
        ),
        StatusCard(
            label="模拟盘",
            value="就绪" if paper_ready else "未就绪",
            status="ok" if paper_ready else "warning",
        ),
        StatusCard(
            label="配置",
            value=config_status,
            status="ok" if config_status == "OK" else "warning",
        ),
        StatusCard(
            label="告警",
            value=alert_status,
            status="ok" if alert_status == "OK" else "warning",
        ),
    ]

    # Account overview from portfolio_snapshot
    account_metrics = {}
    if conn:
        latest_date = get_latest_trade_date(conn, "portfolio_snapshot")
        if latest_date:
            cursor = conn.execute(
                """SELECT total_asset, cash, market_value, total_position_ratio,
                          daily_return, cum_return, drawdown, excess_return
                   FROM portfolio_snapshot
                   WHERE account_id = 'paper' AND trade_date = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (latest_date,),
            )
            row = cursor.fetchone()
            if row:
                account_metrics = {
                    "trade_date": latest_date,
                    "total_asset": row["total_asset"],
                    "cash": row["cash"],
                    "market_value": row["market_value"],
                    "position_ratio": row["total_position_ratio"],
                    "daily_return": row["daily_return"],
                    "cum_return": row["cum_return"],
                    "drawdown": row["drawdown"],
                    "excess_return": row["excess_return"],
                }

    return ApiResponse(
        data={
            "status_cards": [card.model_dump() for card in status_cards],
            "account_metrics": account_metrics,
            "trade_date": account_metrics.get("trade_date"),
            "run_id": daily_summary.get("run_id"),
        }
    )


@router.get("/signals/today")
async def get_today_signals(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
):
    """Get today's trading signals."""
    if not conn:
        return ApiResponse(data={"signals": [], "trade_date": None, "count": 0})

    from quant.core.web.api.deps import MARKET_DB

    market_conn = sqlite3.connect(str(MARKET_DB))
    market_conn.row_factory = sqlite3.Row

    # Get stock name mapping
    name_map = {}
    try:
        cursor = market_conn.execute("SELECT ts_code, name FROM stocks")
        name_map = {row["ts_code"]: row["name"] for row in cursor.fetchall()}
    except Exception:
        pass
    finally:
        market_conn.close()

    # Get latest signals
    latest_date = get_latest_trade_date(conn)
    if not latest_date:
        return ApiResponse(data={"signals": [], "trade_date": None, "count": 0})

    cursor = conn.execute(
        """SELECT ts_code, strategy_id, signal_type, score, price, reason, target_weight
           FROM signal
           WHERE trade_date = ?
           ORDER BY signal_type ASC, score DESC""",
        (latest_date,),
    )

    signals = []
    for row in cursor.fetchall():
        signals.append({
            "ts_code": row["ts_code"],
            "name": name_map.get(row["ts_code"], "-"),
            "strategy_id": row["strategy_id"],
            "signal_type": row["signal_type"],
            "score": row["score"],
            "price": row["price"],
            "reason": row["reason"],
            "target_weight": row["target_weight"],
        })

    return ApiResponse(
        data={
            "signals": signals,
            "trade_date": latest_date,
            "count": len(signals),
        }
    )


@router.get("/positions")
async def get_latest_positions(
    current_user: CurrentUser,
    conn: sqlite3.Connection | None = Depends(get_paper_db),
):
    """Get latest portfolio positions."""
    if not conn:
        return ApiResponse(data={"positions": [], "trade_date": None, "count": 0})

    # Get latest positions date
    cursor = conn.execute(
        "SELECT MAX(trade_date) FROM positions WHERE account_id = 'paper'"
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return ApiResponse(data={"positions": [], "trade_date": None, "count": 0})

    latest_date = row[0]

    # Get stock name mapping
    name_map = get_stock_name_map(conn)

    # Get positions
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
            "ts_code": row["ts_code"],
            "name": name_map.get(row["ts_code"], "-"),
            "quantity": row["quantity"],
            "weight": row["weight"],
            "market_value": row["market_value"],
            "avg_cost": row["avg_cost"],
        })

    return ApiResponse(
        data={
            "positions": positions,
            "trade_date": latest_date,
            "count": len(positions),
        }
    )
