"""Experiments API router with async execution."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body
from pydantic import BaseModel

from quant.apps.web_auth import CurrentUser
from quant.core.experiment.engine import ExperimentConfig, ExperimentEngine
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()
engine = ExperimentEngine()

# In-memory task storage
_experiment_tasks: dict[str, dict[str, Any]] = {}


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


async def _run_experiment_task(task_id: str, experiment_id: str):
    """Run experiment in background."""
    _experiment_tasks[task_id]["status"] = "running"
    _experiment_tasks[task_id]["started_at"] = datetime.now(UTC).isoformat()

    try:
        # Get experiment config
        experiment = engine.get_experiment(experiment_id)
        if not experiment:
            _experiment_tasks[task_id].update({
                "status": "failed",
                "error": "Experiment not found",
                "completed_at": datetime.now(UTC).isoformat(),
            })
            return

        # Create config
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

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, engine.run_grid_search, config)

        _experiment_tasks[task_id].update({
            "status": "completed",
            "total_runs": result.total_runs,
            "best_run": {
                "params": result.best_run.params if result.best_run else {},
                "metrics": result.best_run.metrics if result.best_run else {},
                "score": result.best_run.score if result.best_run else {},
            } if result.best_run else None,
            "completed_at": datetime.now(UTC).isoformat(),
        })

    except Exception as e:
        _experiment_tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now(UTC).isoformat(),
        })


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
async def run_experiment(
    experiment_id: str,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """Run an experiment (async)."""
    experiment = engine.get_experiment(experiment_id)
    if not experiment:
        return ApiResponse(code=404, message="Experiment not found")

    task_id = f"exp_run_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:4]}"

    _experiment_tasks[task_id] = {
        "task_id": task_id,
        "experiment_id": experiment_id,
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
    }

    # Run in background
    background_tasks.add_task(_run_experiment_task, task_id, experiment_id)

    return ApiResponse(data={
        "task_id": task_id,
        "experiment_id": experiment_id,
        "status": "pending",
        "message": "实验已提交运行，请等待完成",
    })


@router.get("/status/{task_id}")
async def get_experiment_status(task_id: str, current_user: CurrentUser):
    """Get experiment task status."""
    task = _experiment_tasks.get(task_id)
    if not task:
        return ApiResponse(code=404, message="Task not found")
    return ApiResponse(data=task)


@router.delete("/{experiment_id}")
async def delete_experiment(experiment_id: str, current_user: CurrentUser):
    """Delete an experiment."""
    db_path = Path("research_store/experiments.sqlite3")
    if not db_path.exists():
        return ApiResponse(code=404, message="Experiment not found")

    conn = sqlite3.connect(str(db_path))
    try:
        # Delete experiment runs first
        conn.execute(
            "DELETE FROM experiment_runs WHERE experiment_id = ?",
            (experiment_id,),
        )
        # Delete experiment
        cursor = conn.execute(
            "DELETE FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return ApiResponse(code=404, message="Experiment not found")

    finally:
        conn.close()

    return ApiResponse(message="Experiment deleted")
