"""Experiments API router with async execution and persistent storage."""
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

TASKS_DB = Path("research_store/experiment_tasks.sqlite3")


def _init_tasks_db():
    """初始化任务数据库。"""
    TASKS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TASKS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiment_tasks (
            task_id TEXT PRIMARY KEY,
            experiment_id TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT DEFAULT '{}',
            error TEXT DEFAULT '',
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _save_task(task_id: str, **kwargs):
    """保存任务到数据库。"""
    conn = sqlite3.connect(str(TASKS_DB))
    try:
        cursor = conn.execute("SELECT task_id FROM experiment_tasks WHERE task_id = ?", (task_id,))
        exists = cursor.fetchone() is not None

        if exists:
            updates = []
            params = []
            for key, value in kwargs.items():
                if key != 'task_id':
                    updates.append(f"{key} = ?")
                    params.append(json.dumps(value) if isinstance(value, (dict, list)) else value)
            if updates:
                params.append(task_id)
                conn.execute(f"UPDATE experiment_tasks SET {', '.join(updates)} WHERE task_id = ?", params)
        else:
            columns = ['task_id'] + [k for k in kwargs.keys() if k != 'task_id']
            placeholders = ', '.join(['?' for _ in columns])
            values = [task_id] + [json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in kwargs.items() if k != 'task_id']
            conn.execute(f"INSERT INTO experiment_tasks ({', '.join(columns)}) VALUES ({placeholders})", values)

        conn.commit()
    finally:
        conn.close()


def _get_task(task_id: str) -> dict[str, Any] | None:
    """从数据库获取任务。"""
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM experiment_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return None

        task = dict(row)
        for field in ['result']:
            if task[field]:
                try:
                    task[field] = json.loads(task[field])
                except:
                    pass
        return task
    finally:
        conn.close()


def _get_tasks_by_experiment(experiment_id: str) -> list[dict[str, Any]]:
    """获取实验的所有任务。"""
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM experiment_tasks WHERE experiment_id = ? ORDER BY created_at DESC",
            (experiment_id,)
        )
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            for field in ['result']:
                if task[field]:
                    try:
                        task[field] = json.loads(task[field])
                    except:
                        pass
            tasks.append(task)
        return tasks
    finally:
        conn.close()


def _update_experiment_status(experiment_id: str, status: str):
    """更新实验状态。"""
    db_path = Path("research_store/experiments.sqlite3")
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE experiments SET status = ? WHERE experiment_id = ?",
            (status, experiment_id),
        )
        conn.commit()
    finally:
        conn.close()


# 初始化数据库
_init_tasks_db()


class CreateExperimentRequest(BaseModel):
    """Request model for creating experiment."""
    name: str
    strategy_id: str
    param_grid: dict[str, Any]
    metric: str = "sharpe"
    universe: str = "all"
    start_date: str = ""
    end_date: str = ""
    rebalance: str = "weekly"
    benchmark_code: str = "000300.SH"


async def _run_experiment_task(task_id: str, experiment_id: str):
    """Run experiment in background."""
    _save_task(task_id, status="running", started_at=datetime.now(UTC).isoformat())
    _update_experiment_status(experiment_id, "running")

    try:
        # Get experiment config
        experiment = engine.get_experiment(experiment_id)
        if not experiment:
            _save_task(
                task_id,
                status="failed",
                error="Experiment not found",
                completed_at=datetime.now(UTC).isoformat(),
            )
            _update_experiment_status(experiment_id, "failed")
            return

        # Create config
        config = ExperimentConfig(
            experiment_id=experiment_id,
            name=experiment["name"],
            strategy_id=experiment["strategy_id"],
            param_grid=experiment["param_grid"],
            metric=experiment.get("metric", "sharpe"),
            universe=experiment.get("universe", "all"),
            start_date=experiment.get("start_date") or "2025-01-01",
            end_date=experiment.get("end_date") or "",
            rebalance=experiment.get("rebalance", "weekly"),
            benchmark_code=experiment.get("benchmark_code", "000300.SH"),
        )

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, engine.run_grid_search, config)

        _save_task(
            task_id,
            status="completed",
            total_runs=result.total_runs,
            best_run={
                "params": result.best_run.params if result.best_run else {},
                "metrics": result.best_run.metrics if result.best_run else {},
                "score": result.best_run.score if result.best_run else {},
            } if result.best_run else None,
            completed_at=datetime.now(UTC).isoformat(),
        )

        _update_experiment_status(experiment_id, "completed")

    except Exception as e:
        _save_task(
            task_id,
            status="failed",
            error=str(e),
            completed_at=datetime.now(UTC).isoformat(),
        )
        _update_experiment_status(experiment_id, "failed")


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

    # 添加任务状态
    tasks = _get_tasks_by_experiment(experiment_id)
    if tasks:
        latest_task = tasks[0]
        experiment["task_status"] = latest_task.get("status")
        experiment["task_error"] = latest_task.get("error")

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
                universe TEXT DEFAULT 'all',
                start_date TEXT DEFAULT '',
                end_date TEXT DEFAULT '',
                rebalance TEXT DEFAULT 'weekly',
                benchmark_code TEXT DEFAULT '000300.SH',
                status TEXT,
                created_at TEXT
            )
        """)
        conn.execute(
            """INSERT INTO experiments
               (experiment_id, name, strategy_id, param_grid, metric, universe, start_date, end_date, rebalance, benchmark_code, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment_id,
                request.name,
                request.strategy_id,
                json.dumps(request.param_grid),
                request.metric,
                request.universe,
                request.start_date,
                request.end_date,
                request.rebalance,
                request.benchmark_code,
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
        "universe": request.universe,
        "start_date": request.start_date,
        "end_date": request.end_date,
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

    # 保存任务
    _save_task(
        task_id,
        experiment_id=experiment_id,
        status="pending",
        created_at=datetime.now(UTC).isoformat(),
    )

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
    task = _get_task(task_id)
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
        conn.execute("DELETE FROM experiment_runs WHERE experiment_id = ?", (experiment_id,))
        cursor = conn.execute("DELETE FROM experiments WHERE experiment_id = ?", (experiment_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return ApiResponse(code=404, message="Experiment not found")
    finally:
        conn.close()

    # 删除任务记录
    conn = sqlite3.connect(str(TASKS_DB))
    try:
        conn.execute("DELETE FROM experiment_tasks WHERE experiment_id = ?", (experiment_id,))
        conn.commit()
    finally:
        conn.close()

    return ApiResponse(message="Experiment deleted")
