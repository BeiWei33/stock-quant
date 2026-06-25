"""Backtest API router with async execution and persistent storage."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import load_report, REPORTS_DIR
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()

ROOT = Path(__file__).resolve().parents[4]
RUN_DIR = ROOT / "research_store" / "web_runs"
TASKS_DB = ROOT / "research_store" / "backtest_tasks.sqlite3"


def _init_tasks_db():
    """初始化任务数据库。"""
    TASKS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TASKS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            params TEXT DEFAULT '{}',
            result TEXT DEFAULT '{}',
            error TEXT DEFAULT '',
            stdout TEXT DEFAULT '',
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
        # 检查任务是否存在
        cursor = conn.execute("SELECT task_id FROM backtest_tasks WHERE task_id = ?", (task_id,))
        exists = cursor.fetchone() is not None

        if exists:
            # 更新现有任务
            updates = []
            params = []
            for key, value in kwargs.items():
                if key != 'task_id':
                    updates.append(f"{key} = ?")
                    params.append(json.dumps(value) if isinstance(value, (dict, list)) else value)
            if updates:
                params.append(task_id)
                conn.execute(f"UPDATE backtest_tasks SET {', '.join(updates)} WHERE task_id = ?", params)
        else:
            # 插入新任务
            columns = ['task_id'] + [k for k in kwargs.keys() if k != 'task_id']
            placeholders = ', '.join(['?' for _ in columns])
            values = [task_id] + [json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in kwargs.items() if k != 'task_id']
            conn.execute(f"INSERT INTO backtest_tasks ({', '.join(columns)}) VALUES ({placeholders})", values)

        conn.commit()
    finally:
        conn.close()


def _get_task(task_id: str) -> dict[str, Any] | None:
    """从数据库获取任务。"""
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM backtest_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return None

        task = dict(row)
        # 解析 JSON 字段
        for field in ['params', 'result']:
            if task[field]:
                try:
                    task[field] = json.loads(task[field])
                except:
                    pass
        return task
    finally:
        conn.close()


def _get_all_tasks() -> list[dict[str, Any]]:
    """获取所有任务。"""
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM backtest_tasks ORDER BY created_at DESC LIMIT 50")
        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            for field in ['params', 'result']:
                if task[field]:
                    try:
                        task[field] = json.loads(task[field])
                    except:
                        pass
            tasks.append(task)
        return tasks
    finally:
        conn.close()


def _delete_task(task_id: str) -> bool:
    """删除任务。"""
    conn = sqlite3.connect(str(TASKS_DB))
    try:
        cursor = conn.execute("DELETE FROM backtest_tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# 初始化数据库
_init_tasks_db()


def _get_python_exe() -> str:
    """Get the correct Python executable path."""
    import shutil
    exe = Path(sys.executable)
    if exe.exists() and "WindowsApps" not in str(exe):
        return str(exe)
    candidates = [
        Path(r"D:\AI\apps\exe\anaconda3\python.exe"),
        Path.home() / "anaconda3" / "python.exe",
        Path.home() / "miniconda3" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    python_path = shutil.which("python")
    if python_path and "WindowsApps" not in python_path:
        return python_path
    return sys.executable


PYTHON_EXE = _get_python_exe()


async def _run_backtest_task(
    task_id: str,
    start_date: str,
    end_date: str,
    strategy: str,
    rebalance: str,
    limit: str,
    use_local: bool,
    universe: str,
):
    """Run backtest in background."""
    import os

    _save_task(task_id, status="running", started_at=datetime.now(UTC).isoformat())

    # Check if using local data
    local_db = ROOT / "research_store" / "market_data.sqlite3"
    if use_local and local_db.exists():
        cmd_parts = [
            PYTHON_EXE, "-m", "quant.apps.backtest",
            f'--sqlite={local_db}',
            f'--start-date={start_date}',
            f'--end-date={end_date}',
            f'--strategy={strategy}',
            f'--rebalance={rebalance}',
            f'--output={ROOT / "research_store" / "reports" / "akshare_backtest.json"}',
        ]
        if universe and universe != "all":
            cmd_parts.append(f'--universe={universe}')
    else:
        cmd_parts = [
            PYTHON_EXE, "-X", "utf8", "-m",
            "quant.apps.start", "akshare-backtest",
            f'--start-date={start_date}',
            f'--end-date={end_date}',
        ]
        if rebalance:
            cmd_parts.append(f'--rebalance={rebalance}')
        if limit:
            cmd_parts.append(f'--limit={limit}')

    # Set PYTHONPATH
    python_path = str(ROOT)
    if "PYTHONPATH" in os.environ:
        python_path = python_path + os.pathsep + os.environ["PYTHONPATH"]

    if os.name == 'nt':
        cmd_parts_str = [f'"{c}"' if ' ' in c else c for c in cmd_parts]
        cmd_str = f'set "PYTHONPATH={python_path}" && {" ".join(cmd_parts_str)}'
    else:
        cmd_str = ' '.join(cmd_parts)

    print(f"[Backtest {task_id}] Running: {cmd_str}")

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ROOT),
        )

        stdout, stderr = await proc.communicate()
        stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ''
        stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ''

        print(f"[Backtest {task_id}] Return code: {proc.returncode}")

        if proc.returncode == 0:
            result = load_report("akshare_backtest.json")
            _save_task(
                task_id,
                status="completed",
                result=result,
                completed_at=datetime.now(UTC).isoformat(),
            )
        else:
            _save_task(
                task_id,
                status="failed",
                error=stderr_str[-500:] if stderr_str else "Unknown error",
                stdout=stdout_str[-500:],
                completed_at=datetime.now(UTC).isoformat(),
            )

    except Exception as e:
        _save_task(
            task_id,
            status="failed",
            error=str(e),
            completed_at=datetime.now(UTC).isoformat(),
        )


@router.get("/results")
async def get_backtest_results(current_user: CurrentUser):
    """Get latest backtest results."""
    for filename in ["akshare_backtest.json", "backtest.json", "sample_backtest.json"]:
        result = load_report(filename)
        if result:
            return ApiResponse(data=result)
    return ApiResponse(data=None, message="No backtest results found")


@router.get("/experiments")
async def get_experiments(current_user: CurrentUser):
    """Get backtest experiment list."""
    experiments = load_report("backtest_experiments.json")
    if not isinstance(experiments, list):
        experiments = []
    return ApiResponse(data=experiments)


@router.post("/run")
async def run_backtest(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)", min_length=10),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)", min_length=10),
    strategy: str = Query("momentum_rank", description="Strategy ID"),
    rebalance: str = Query("weekly", description="Rebalance frequency"),
    limit: str = Query("", description="Stock limit"),
    use_local: bool = Query(False, description="Use local market data instead of fetching"),
    universe: str = Query("all", description="Stock universe (all/csi300/csi500/csi800)"),
):
    """Submit a backtest task (async)."""
    task_id = f"backtest_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:4]}"

    # 保存任务到数据库
    _save_task(
        task_id,
        status="pending",
        params={
            "start_date": start_date,
            "end_date": end_date,
            "strategy": strategy,
            "rebalance": rebalance,
            "universe": universe,
        },
        created_at=datetime.now(UTC).isoformat(),
    )

    # Run in background
    background_tasks.add_task(
        _run_backtest_task,
        task_id,
        start_date,
        end_date,
        strategy,
        rebalance,
        limit,
        use_local,
        universe,
    )

    return ApiResponse(data={
        "task_id": task_id,
        "status": "pending",
        "message": "回测任务已提交，请等待完成",
    })


@router.get("/status/{task_id}")
async def get_backtest_status(task_id: str, current_user: CurrentUser):
    """Get backtest task status."""
    task = _get_task(task_id)
    if not task:
        return ApiResponse(code=404, message="Task not found")
    return ApiResponse(data=task)


@router.get("/tasks")
async def list_backtest_tasks(current_user: CurrentUser):
    """List all backtest tasks."""
    tasks = _get_all_tasks()
    return ApiResponse(data=tasks)


@router.delete("/tasks/{task_id}")
async def delete_backtest_task(task_id: str, current_user: CurrentUser):
    """Delete a backtest task."""
    if _delete_task(task_id):
        return ApiResponse(message="Task deleted")
    return ApiResponse(code=404, message="Task not found")
