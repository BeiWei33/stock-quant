"""Tasks API router with async execution and WebSocket progress."""
from __future__ import annotations

import asyncio
import os
import random
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from quant.apps.web_auth import CurrentUser
from quant.apps.web_ws import TaskStatus, ws_manager
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()

ROOT = Path(__file__).resolve().parents[4]
RUN_DIR = ROOT / "research_store" / "web_runs"


def _get_python_exe() -> str:
    """Get the correct Python executable path, avoiding Windows Store stub."""
    # Check if current sys.executable is valid (not Windows Store stub)
    exe = Path(sys.executable)
    if exe.exists() and "WindowsApps" not in str(exe):
        return str(exe)

    # Try to find Anaconda Python
    candidates = [
        Path(r"D:\AI\apps\exe\anaconda3\python.exe"),
        Path.home() / "anaconda3" / "python.exe",
        Path.home() / "miniconda3" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Fallback: try to find python in PATH (excluding WindowsApps)
    python_path = shutil.which("python")
    if python_path and "WindowsApps" not in python_path:
        return python_path

    # Last resort: use sys.executable
    return sys.executable


PYTHON_EXE = _get_python_exe()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time task progress updates."""
    client_id = f"client_{random.randrange(1000, 9999)}"
    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            # Echo back or handle commands
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)


@router.get("/list")
async def get_task_list(current_user: CurrentUser):
    """Get all tasks with their status."""
    tasks = ws_manager.get_all_tasks()
    return ApiResponse(data=[task.to_dict() for task in tasks])


@router.get("/{task_id}")
async def get_task_status(task_id: str, current_user: CurrentUser):
    """Get task status by ID."""
    task = ws_manager.get_task(task_id)
    if not task:
        return ApiResponse(code=404, message="Task not found")
    return ApiResponse(data=task.to_dict())


@router.post("/daily")
async def run_daily(current_user: CurrentUser):
    """Run daily workflow with async execution."""
    return await _run_task_async("daily", [PYTHON_EXE, "-m", "quant.apps.start", "daily"])


@router.post("/stock-pick")
async def run_stock_pick(
    current_user: CurrentUser,
    scope: str = "30",
    price_min: str = "",
    price_max: str = "",
):
    """Run stock picking with async execution."""
    cmd = [PYTHON_EXE, "-X", "utf8", "-m", "quant.apps.daily", "--source", "auto", "--no-lock"]
    if scope == "all":
        cmd.append("--akshare-all")
    else:
        cmd.extend(["--akshare-limit", "30"])
    if price_min:
        cmd.extend(["--price-min", price_min])
    if price_max:
        cmd.extend(["--price-max", price_max])

    return await _run_task_async("stock-pick", cmd)


@router.post("/doctor")
async def run_doctor(current_user: CurrentUser):
    """Run system doctor check."""
    return await _run_task_async("doctor", [PYTHON_EXE, "-m", "quant.apps.start", "doctor"])


@router.post("/snapshot")
async def run_snapshot(current_user: CurrentUser):
    """Run snapshot archive."""
    return await _run_task_async("snapshot", [PYTHON_EXE, "-m", "quant.apps.start", "snapshot"])


@router.post("/reset-paper")
async def reset_paper(current_user: CurrentUser, initial_cash: float = 10000.0):
    """Reset paper trading with new initial cash."""
    import sqlite3

    # Update config
    config_path = ROOT / "config" / "daily.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            if "workflow" not in cfg:
                cfg["workflow"] = {}
            cfg["workflow"]["initial_cash"] = initial_cash
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to update config: {e}"}

    # Clear database
    db_path = ROOT / "research_store" / "paper_trading.sqlite3"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cu = conn.cursor()
            tables_to_clear = [
                "event_log", "order_fill", "order_intent", "order_risk_check",
                "portfolio_snapshot", "positions", "reconciliation_report", "signal",
                "universe_snapshot", "workflow_lock", "workflow_run",
            ]
            cleared = []
            for t in tables_to_clear:
                try:
                    cu.execute(f"DELETE FROM {t}")
                    cleared.append(f"{t}: {cu.rowcount} rows")
                except:
                    pass
            conn.commit()

            # Create initial snapshot
            from datetime import UTC, datetime
            today_str = datetime.now(UTC).strftime("%Y-%m-%d")
            cu.execute(
                "INSERT OR REPLACE INTO portfolio_snapshot (account_id, trade_date, total_asset, cash, market_value, total_position_ratio, daily_return, cum_return, drawdown) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("paper", today_str, initial_cash, initial_cash, 0.0, 0.0, 0.0, 0.0, 0.0)
            )
            conn.commit()
            conn.close()

            return {
                "status": "OK",
                "message": f"模拟盘已重置，初始资金 {initial_cash:,.0f}",
                "cleared": cleared,
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to reset database: {e}"}

    return {"status": "OK", "message": "Database not found, config updated"}


@router.post("/backtest")
async def run_backtest_task(
    current_user: CurrentUser,
    start_date: str = "",
    end_date: str = "",
    rebalance: str = "weekly",
    limit: str = "",
    use_local: bool = False,
):
    """Run backtest with async execution."""
    local_db = ROOT / "research_store" / "market_data.sqlite3"

    if use_local and local_db.exists():
        # Run backtest directly on local data
        cmd = [
            PYTHON_EXE, "-m", "quant.apps.backtest",
            f"--sqlite={local_db}",
            f"--output={ROOT / 'research_store' / 'reports' / 'akshare_backtest.json'}",
        ]
        if start_date:
            cmd.extend(["--start-date", start_date])
        if end_date:
            cmd.extend(["--end-date", end_date])
        if rebalance:
            cmd.extend(["--rebalance", rebalance])
    else:
        # Fetch new data and run backtest
        cmd = [PYTHON_EXE, "-X", "utf8", "-m", "quant.apps.start", "akshare-backtest"]

        if start_date:
            cmd.extend(["--start-date", start_date])
        if end_date:
            cmd.extend(["--end-date", end_date])
        if rebalance:
            cmd.extend(["--rebalance", rebalance])
        if limit:
            cmd.extend(["--limit", limit])

    return await _run_task_async("backtest", cmd)


async def _run_task_async(action: str, command: list[str]) -> dict:
    """Execute a task asynchronously with progress updates."""
    task_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"_{random.randrange(1000, 9999)}"

    # Create task in manager
    task = ws_manager.create_task(task_id, action)

    # Start async execution
    asyncio.create_task(_execute_task(task_id, command))

    return {
        "task_id": task_id,
        "action": action,
        "status": TaskStatus.PENDING.value,
        "message": "Task submitted",
    }


async def _execute_task(task_id: str, command: list[str]):
    """Execute subprocess asynchronously and stream output."""
    await ws_manager.update_task(task_id, status=TaskStatus.RUNNING, step_name="Starting...")

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUN_DIR / f"{task_id}.log"

    stdout_lines = []
    stderr_lines = []

    # Set environment to include project root in Python path
    import os
    env = os.environ.copy()
    # Ensure project root is in PYTHONPATH
    python_path = str(ROOT)
    if "PYTHONPATH" in env:
        python_path = python_path + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = python_path

    # Build command string with PYTHONPATH for Windows
    if os.name == 'nt':
        # Windows: use set to set PYTHONPATH before running command
        cmd_parts = [f'"{c}"' if ' ' in c else c for c in command]
        cmd_str = f'set "PYTHONPATH={python_path}" && {" ".join(cmd_parts)}'
    else:
        cmd_str = ' '.join(command)

    print(f"[Task {task_id}] Executing: {cmd_str}")

    try:
        # Create async subprocess
        proc = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ROOT),
        )

        # Read stdout line by line
        async def read_stdout():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                stdout_lines.append(decoded)

                # Update progress with last few lines
                tail = "\n".join(stdout_lines[-5:])
                await ws_manager.update_task(
                    task_id,
                    stdout_tail=tail,
                    step_name=_extract_step_name(decoded),
                )

        # Read stderr line by line
        async def read_stderr():
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                stderr_lines.append(decoded)

                tail = "\n".join(stderr_lines[-3:])
                await ws_manager.update_task(task_id, stderr_tail=tail)

        # Run readers concurrently
        await asyncio.gather(read_stdout(), read_stderr())

        # Wait for process to complete
        return_code = await proc.wait()

        # Determine final status
        if return_code == 0:
            status = TaskStatus.OK
        else:
            status = TaskStatus.FAIL

        await ws_manager.update_task(
            task_id,
            status=status,
            return_code=return_code,
            step_name="Completed",
        )

    except asyncio.TimeoutError:
        await ws_manager.update_task(
            task_id,
            status=TaskStatus.TIMEOUT,
            step_name="Timed out after 600s",
        )
    except FileNotFoundError:
        await ws_manager.update_task(
            task_id,
            status=TaskStatus.FAIL,
            step_name=f"Python not found: {command[0]}",
        )
    except Exception as e:
        await ws_manager.update_task(
            task_id,
            status=TaskStatus.FAIL,
            step_name=f"Error: {str(e)}",
        )

    # Write log file
    try:
        log_content = f"task_id: {task_id}\ncommand: {' '.join(command)}\n\n--- stdout ---\n" + "\n".join(stdout_lines) + "\n\n--- stderr ---\n" + "\n".join(stderr_lines)
        log_path.write_text(log_content, encoding="utf-8")
    except Exception:
        pass


def _extract_step_name(line: str) -> str:
    """Extract a meaningful step name from stdout line."""
    # Try to extract step indicators
    if "[" in line and "]" in line:
        start = line.find("[")
        end = line.find("]", start)
        if end > start:
            return line[start + 1 : end]

    # Common patterns
    patterns = [
        "Collecting",
        "Processing",
        "Calculating",
        "Generating",
        "Loading",
        "Saving",
        "Running",
        "Completed",
        "Success",
        "Error",
    ]

    for pattern in patterns:
        if pattern.lower() in line.lower():
            return line[:50] + "..." if len(line) > 50 else line

    # Return truncated line
    return line[:50] + "..." if len(line) > 50 else line if line else "Processing..."
