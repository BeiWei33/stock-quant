"""Experiments API router."""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel

from quant.apps.web_auth import CurrentUser
from quant.core.experiment.engine import ExperimentConfig, ExperimentEngine
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()
engine = ExperimentEngine()


class CreateExperimentRequest(BaseModel):
    """Request model for creating experiment."""
    name: str
    strategy_id: str
    param_grid: dict[str, Any]
    metric: str = "sharpe"
    start_date: str = "2025-01-01"
    end_date: str = ""
    rebalance: str = "weekly"
    benchmark_code: str = "000300.SH"


@router.get("")
async def list_experiments(current_user: CurrentUser):
    """List all experiments."""
    experiments = engine.list_experiments()
    return ApiResponse(data=experiments)


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str, current_user: CurrentUser):
    """Get experiment details."""
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return ApiResponse(code=404, message="Experiment not found")
    return ApiResponse(data=experiment)


@router.post("")
async def create_experiment(
    current_user: CurrentUser,
    request: CreateExperimentRequest = Body(...),
):
    """Create a new experiment."""
    import uuid

    experiment_id = f"exp_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:4]}"

    # Save experiment config
    db_path = Path("research_store/experiments.sqlite3")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT,
                strategy_id TEXT,
                param_grid TEXT,
                metric TEXT,
                status TEXT,
                created_at TEXT
            )
        """)
        conn.execute(
            """INSERT INTO experiments
               (experiment_id, name, strategy_id, param_grid, metric, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment_id,
                request.name,
                request.strategy_id,
                json.dumps(request.param_grid),
                request.metric,
                "created",
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return ApiResponse(data={
        "experiment_id": experiment_id,
        "name": request.name,
        "strategy_id": request.strategy_id,
        "status": "created",
    })


@router.post("/{experiment_id}/run")
async def run_experiment(experiment_id: str, current_user: CurrentUser):
    """Run an experiment."""
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return ApiResponse(code=404, message="Experiment not found")

    # Create config from saved experiment
    config = ExperimentConfig(
        experiment_id=experiment_id,
        name=experiment["name"],
        strategy_id=experiment["strategy_id"],
        param_grid=experiment["param_grid"],
        metric=experiment.get("metric", "sharpe"),
        start_date="2025-01-01",
        end_date="",
        rebalance="weekly",
        benchmark_code="000300.SH",
    )

    # Run experiment
    try:
        result = engine.run_grid_search(config)
        return ApiResponse(data={
            "experiment_id": experiment_id,
            "status": "completed",
            "total_runs": result.total_runs,
            "best_run": {
                "params": result.best_run.params if result.best_run else {},
                "metrics": result.best_run.metrics if result.best_run else {},
                "score": result.best_run.score if result.best_run else {},
            } if result.best_run else None,
        })
    except Exception as e:
        return ApiResponse(code=500, message=f"Experiment failed: {str(e)}")
