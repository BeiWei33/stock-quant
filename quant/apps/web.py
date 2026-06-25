"""Personal Quant Web Console -- FastAPI application.

Usage:
    python -m quant.apps.web                  # Start FastAPI server
    python -m quant.apps.web --legacy         # Start legacy http.server
    python -m quant.apps.web --port 8001      # Custom port
"""
from __future__ import annotations

import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: ensure directories exist
    (ROOT / "research_store" / "web_runs").mkdir(parents=True, exist_ok=True)
    (ROOT / "research_store" / "web_uploads").mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown: cleanup if needed


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Personal Quant API",
        description="A-share quant research and paper-trading system",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and register routers
    from quant.core.web.api.auth import router as auth_router
    from quant.core.web.api.backtest import router as backtest_router
    from quant.core.web.api.dashboard import router as dashboard_router
    from quant.core.web.api.experiments import router as experiments_router
    from quant.core.web.api.market import router as market_router
    from quant.core.web.api.monitoring import router as monitoring_router
    from quant.core.web.api.notification import router as notification_router
    from quant.core.web.api.positions import router as positions_router
    from quant.core.web.api.signals import router as signals_router
    from quant.core.web.api.tasks import router as tasks_router
    from quant.core.web.api.advanced_analysis import router as advanced_analysis_router

    # Public routes (no auth required)
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

    # WebSocket endpoint (no auth)
    from quant.core.web.api.tasks import websocket_endpoint
    app.add_api_websocket_route("/api/tasks/ws", websocket_endpoint)

    # Protected routes
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
    app.include_router(signals_router, prefix="/api/signals", tags=["signals"])
    app.include_router(positions_router, prefix="/api/positions", tags=["positions"])
    app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
    app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(backtest_router, prefix="/api/backtest", tags=["backtest"])
    app.include_router(experiments_router, prefix="/api/experiments", tags=["experiments"])
    app.include_router(market_router, prefix="/api/market", tags=["market"])
    app.include_router(notification_router, prefix="/api/notification", tags=["notification"])
    app.include_router(advanced_analysis_router, prefix="/api/advanced-analysis", tags=["advanced-analysis"])

    # Note: WebSocket endpoint is now in tasks_router at /api/tasks/ws

    # Health check endpoint
    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    # Serve frontend static files (production)
    frontend_dist = ROOT / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Personal Quant web console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--legacy", action="store_true", help="Run legacy http.server")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.legacy:
        # Run legacy http.server
        from quant.apps.web_legacy import main as legacy_main
        legacy_main()
        return

    # Run FastAPI with uvicorn
    import uvicorn

    print(f"Personal Quant Web Console (FastAPI): http://{args.host}:{args.port}/")
    print(f"API Documentation: http://{args.host}:{args.port}/docs")
    print("Press Ctrl+C to stop.")

    uvicorn.run(
        "quant.apps.web:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
