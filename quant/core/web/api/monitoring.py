"""Monitoring API router."""
from __future__ import annotations

from fastapi import APIRouter

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import load_monitoring
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()


@router.get("/health")
async def get_system_health(current_user: CurrentUser):
    """Get system health status."""
    readiness = load_monitoring("readiness.json")
    return ApiResponse(data=readiness)


@router.get("/alerts")
async def get_alerts(current_user: CurrentUser):
    """Get system alerts."""
    alerts = load_monitoring("alerts.json")
    return ApiResponse(data=alerts)


@router.get("/config")
async def get_config_health(current_user: CurrentUser):
    """Get configuration health status."""
    config_health = load_monitoring("config_health.json")
    return ApiResponse(data=config_health)


@router.get("/status")
async def get_status_summary(current_user: CurrentUser):
    """Get overall status summary."""
    daily_summary = load_monitoring("daily_summary.json") or {}
    readiness = load_monitoring("readiness.json") or {}
    alerts = load_monitoring("alerts.json") or {}

    return ApiResponse(
        data={
            "run_status": daily_summary.get("run_status", "N/A"),
            "paper_ready": readiness.get("paper_ready", False),
            "live_ready": readiness.get("live_ready", False),
            "alert_status": alerts.get("status", "OK"),
            "highest_severity": alerts.get("highest_severity", "INFO"),
        }
    )
