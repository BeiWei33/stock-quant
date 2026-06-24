"""Experiments API router."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from quant.apps.web_auth import CurrentUser
from quant.core.experiment.engine import ExperimentConfig, ExperimentEngine
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()
engine = ExperimentEngine()


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
    name: str = Query(..., description="Experiment name"),
    strategy_id: str = Query(..., description="Strategy ID"),
    param_grid: str = Query(..., description="Parameter grid (JSON)"),
    metric: str = Query("sharpe", description="Optimization metric"),
    start_date: str = Query("2025-01-01", description="Start date"),
    end_date: str = Query("", description="End date"),
    rebalance: str = Query("weekly", description="Rebalance frequency"),
    benchmark_code: str = Query("000300.SH", description="Benchmark code"),
):
    """Create a new experiment."""
    import uuid
    from datetime import UTC, datetime

    try:
        params = json.loads(param_grid)
    except json.JSONDecodeError as e:
        return ApiResponse(code=400, message=f"Invalid param_grid JSON: {e}")

    experiment_id = f"exp_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:4]}"

    config = ExperimentConfig(
        experiment_id=experiment_id,
        name=name,
        strategy_id=strategy_id,
        param_grid=params,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        rebalance=rebalance,
        benchmark_code=benchmark_code,
    )

    # Save experiment config (don't run yet)
    import sqlite3
    from datetime import UTC, datetime

    db_path = Path("research_store/experiments.sqlite3")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT OR REPLACE INTO experiments
               (experiment_id, name, strategy_id, param_grid, metric, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment_id,
                name,
                strategy_id,
                json.dumps(params),
                metric,
                "created",
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return ApiResponse(data={
        "experiment_id": experiment_id,
        "name": name,
        "strategy_id": strategy_id,
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
