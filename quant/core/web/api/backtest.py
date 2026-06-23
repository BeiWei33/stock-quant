"""Backtest API router."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from quant.apps.web_auth import CurrentUser
from quant.core.web.api.deps import load_report, REPORTS_DIR
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()
# backtest.py is at quant/core/web/api/backtest.py, so parents[4] is project root
ROOT = Path(__file__).resolve().parents[4]


@router.get("/results")
async def get_backtest_results(current_user: CurrentUser):
    """Get latest backtest results."""
    # Try to load the latest backtest result
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


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str, current_user: CurrentUser):
    """Get single experiment by ID."""
    experiments = load_report("backtest_experiments.json")
    if not isinstance(experiments, list):
        return ApiResponse(code=404, message="Experiment not found")

    for exp in experiments:
        if isinstance(exp, dict) and exp.get("experiment_id") == experiment_id:
            return ApiResponse(data=exp)

    return ApiResponse(code=404, message="Experiment not found")


@router.post("/run")
async def run_backtest(
    current_user: CurrentUser,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)", min_length=10),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)", min_length=10),
    rebalance: str = Query("weekly", description="Rebalance frequency"),
    limit: str = Query("", description="Stock limit"),
):
    """Submit a backtest task."""
    import os

    # Use python command directly (not sys.executable which might be different)
    python_cmd = "python"

    cmd_parts = [
        python_cmd, "-X", "utf8", "-m",
        "quant.apps.start", "akshare-backtest",
        f'--start-date={start_date}',
        f'--end-date={end_date}',
    ]

    if rebalance:
        cmd_parts.append(f'--rebalance={rebalance}')
    if limit:
        cmd_parts.append(f'--limit={limit}')

    # Set PYTHONPATH and run
    python_path = str(ROOT)
    if "PYTHONPATH" in os.environ:
        python_path = python_path + os.pathsep + os.environ["PYTHONPATH"]

    cmd_str = f'set "PYTHONPATH={python_path}" && {" ".join(cmd_parts)}'

    print(f"[Backtest] Running: {cmd_str}")

    # Run backtest
    try:
        proc = subprocess.run(
            cmd_str,
            capture_output=True,
            timeout=600,
            cwd=str(ROOT),
            shell=True,
        )

        # Decode output with fallback encoding
        stdout = proc.stdout.decode('utf-8', errors='replace') if proc.stdout else ''
        stderr = proc.stderr.decode('utf-8', errors='replace') if proc.stderr else ''

        print(f"[Backtest] Return code: {proc.returncode}")
        if stdout:
            print(f"[Backtest] stdout: {stdout[:200]}")
        if stderr:
            print(f"[Backtest] stderr: {stderr[:200]}")

        if proc.returncode == 0:
            # Load and return results
            result = load_report("akshare_backtest.json")
            return ApiResponse(
                data={
                    "status": "OK",
                    "return_code": proc.returncode,
                    "result": result,
                    "stdout": stdout[-500:] if stdout else "",
                }
            )
        else:
            return ApiResponse(
                code=500,
                message="Backtest failed",
                data={
                    "status": "FAIL",
                    "return_code": proc.returncode,
                    "stderr": stderr[-500:] if stderr else "",
                    "stdout": stdout[-500:] if stdout else "",
                }
            )
    except subprocess.TimeoutExpired:
        return ApiResponse(
            code=500,
            message="Backtest timed out",
            data={"status": "TIMEOUT"}
        )
    except Exception as e:
        return ApiResponse(
            code=500,
            message=str(e),
            data={"status": "ERROR"}
        )
