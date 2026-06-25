"""高级回测分析 API。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from quant.apps.web_auth import CurrentUser
from quant.core.web.schemas.common import ApiResponse

router = APIRouter()

ROOT = Path(__file__).resolve().parents[4]


def _get_python_exe() -> str:
    """获取 Python 可执行文件路径。"""
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


@router.get("/out-of-sample")
async def run_out_of_sample_test(
    current_user: CurrentUser,
    strategy: str = Query("momentum_rank", description="Strategy ID"),
    start_date: str = Query("2020-01-01", description="Start date"),
    end_date: str = Query("2026-06-24", description="End date"),
    train_ratio: float = Query(0.6, description="Train set ratio"),
    val_ratio: float = Query(0.2, description="Validation set ratio"),
    test_ratio: float = Query(0.2, description="Test set ratio"),
):
    """运行样本外测试。"""
    import sqlite3

    db_path = ROOT / "research_store" / "market_data.sqlite3"
    if not db_path.exists():
        return ApiResponse(code=404, message="Market data not found")

    try:
        from quant.core.backtest.out_of_sample import OutOfSampleTester
        from quant.core.backtest.engine import BacktestEngine
        from quant.core.strategy.factory import build_strategy
        from quant.core.persistence.sqlite_store import SqliteStore
        from datetime import date

        store = SqliteStore(db_path)
        bars = store.load_daily_bars(
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
        )
        stocks = store.load_stocks()
        benchmark_bars = store.load_benchmark_bars("000300.SH")

        strategy_instance = build_strategy(strategy)
        engine = BacktestEngine()

        tester = OutOfSampleTester(engine)
        results = tester.run_out_of_sample_test(
            strategy=strategy_instance,
            bars=bars,
            stocks=stocks,
            benchmark_bars=benchmark_bars,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
        )

        analysis = tester.analyze_overfit_risk(results)

        # 转换结果为可序列化格式
        result_data = {
            "analysis": analysis,
            "periods": [
                {
                    "name": r.period.name,
                    "start_date": str(r.period.start_date),
                    "end_date": str(r.period.end_date),
                    "is_train": r.is_train,
                    "metrics": {
                        "total_return": r.metrics.get("total_return", 0),
                        "annual_return": r.metrics.get("annual_return", 0),
                        "sharpe": r.metrics.get("sharpe", 0),
                        "max_drawdown": r.metrics.get("max_drawdown", 0),
                    },
                }
                for r in results
            ],
        }

        return ApiResponse(data=result_data)

    except Exception as e:
        return ApiResponse(code=500, message=f"Out-of-sample test failed: {str(e)}")


@router.get("/multi-benchmark")
async def run_multi_benchmark_test(
    current_user: CurrentUser,
    strategy: str = Query("momentum_rank", description="Strategy ID"),
    start_date: str = Query("2025-01-01", description="Start date"),
    end_date: str = Query("2026-06-24", description="End date"),
):
    """运行多基准对比测试。"""
    import sqlite3

    db_path = ROOT / "research_store" / "market_data.sqlite3"
    if not db_path.exists():
        return ApiResponse(code=404, message="Market data not found")

    try:
        from quant.core.backtest.multi_benchmark import MultiBenchmarkTester
        from quant.core.backtest.engine import BacktestEngine
        from quant.core.strategy.factory import build_strategy
        from quant.core.persistence.sqlite_store import SqliteStore
        from datetime import date

        store = SqliteStore(db_path)
        bars = store.load_daily_bars(
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
        )
        stocks = store.load_stocks()

        # 获取所有可用的基准
        benchmark_bars_dict = {}
        for benchmark_code in ["000300.SH", "000905.SH", "equal_weight"]:
            benchmark_bars = store.load_benchmark_bars(benchmark_code)
            if benchmark_bars is not None and not benchmark_bars.empty:
                benchmark_bars_dict[benchmark_code] = benchmark_bars

        if not benchmark_bars_dict:
            return ApiResponse(code=404, message="No benchmark data found")

        strategy_instance = build_strategy(strategy)
        engine = BacktestEngine()

        tester = MultiBenchmarkTester(engine)
        result = tester.run_multi_benchmark_test(
            strategy=strategy_instance,
            bars=bars,
            stocks=stocks,
            benchmark_bars_dict=benchmark_bars_dict,
        )

        # 转换结果为可序列化格式
        result_data = {
            "strategy_name": result.strategy_name,
            "strategy_metrics": {
                "total_return": result.strategy_metrics.get("total_return", 0),
                "annual_return": result.strategy_metrics.get("annual_return", 0),
                "sharpe": result.strategy_metrics.get("sharpe", 0),
                "max_drawdown": result.strategy_metrics.get("max_drawdown", 0),
            },
            "best_benchmark": result.best_benchmark,
            "comparisons": [
                {
                    "benchmark_code": c.benchmark_code,
                    "benchmark_name": c.benchmark_name,
                    "excess_return": c.excess_return,
                    "information_ratio": c.information_ratio,
                    "tracking_error": c.tracking_error,
                    "beta": c.beta,
                    "correlation": c.correlation,
                    "benchmark_metrics": c.benchmark_metrics,
                }
                for c in result.comparisons
            ],
        }

        # 生成报告
        report = tester.generate_comparison_report(result)
        result_data["report"] = report

        return ApiResponse(data=result_data)

    except Exception as e:
        return ApiResponse(code=500, message=f"Multi-benchmark test failed: {str(e)}")


@router.get("/monte-carlo")
async def run_monte_carlo_test(
    current_user: CurrentUser,
    strategy: str = Query("momentum_rank", description="Strategy ID"),
    start_date: str = Query("2025-01-01", description="Start date"),
    end_date: str = Query("2026-06-24", description="End date"),
    n_simulations: int = Query(50, description="Number of simulations"),
):
    """运行蒙特卡洛测试。"""
    import sqlite3

    db_path = ROOT / "research_store" / "market_data.sqlite3"
    if not db_path.exists():
        return ApiResponse(code=404, message="Market data not found")

    try:
        from quant.core.backtest.monte_carlo import MonteCarloTester
        from quant.core.backtest.engine import BacktestEngine
        from quant.core.strategy.factory import build_strategy
        from quant.core.strategy.momentum import MomentumRankStrategy
        from quant.core.persistence.sqlite_store import SqliteStore
        from datetime import date

        store = SqliteStore(db_path)
        bars = store.load_daily_bars(
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
        )
        stocks = store.load_stocks()
        benchmark_bars = store.load_benchmark_bars("000300.SH")

        strategy_instance = build_strategy(strategy)
        engine = BacktestEngine()

        tester = MonteCarloTester(engine)

        # 运行 Bootstrap 测试
        bootstrap_results = tester.run_bootstrap_test(
            strategy=strategy_instance,
            bars=bars,
            stocks=stocks,
            benchmark_bars=benchmark_bars,
            n_simulations=n_simulations,
            sample_ratio=0.8,
        )

        # 运行参数扰动测试
        param_results = tester.run_parameter_perturbation_test(
            strategy_class=MomentumRankStrategy,
            base_params={"max_holdings": 20},
            bars=bars,
            stocks=stocks,
            benchmark_bars=benchmark_bars,
            n_simulations=n_simulations,
            perturbation_range=0.2,
        )

        # 分析结果
        bootstrap_analysis = tester.analyze_results(bootstrap_results, "sharpe")
        param_analysis = tester.analyze_results(param_results, "sharpe")

        # 获取实际指标
        actual_result = engine.run(
            __import__("quant.core.backtest.engine", fromlist=["BacktestRequest"]).BacktestRequest(
                bars=bars,
                stocks=stocks,
                strategy=strategy_instance,
                benchmark_bars=benchmark_bars,
                initial_cash=1_000_000,
                rebalance="weekly",
            )
        )

        # 生成报告
        report = tester.generate_report(
            bootstrap_results=bootstrap_results,
            parameter_results=param_results,
            actual_metrics=actual_result.metrics,
        )

        result_data = {
            "bootstrap": {
                "n_simulations": bootstrap_analysis.n_simulations,
                "mean": bootstrap_analysis.mean,
                "std": bootstrap_analysis.std,
                "min": bootstrap_analysis.min_val,
                "max": bootstrap_analysis.max_val,
                "percentile_5": bootstrap_analysis.percentile_5,
                "percentile_50": bootstrap_analysis.percentile_50,
                "percentile_95": bootstrap_analysis.percentile_95,
            },
            "parameter": {
                "n_simulations": param_analysis.n_simulations,
                "mean": param_analysis.mean,
                "std": param_analysis.std,
                "min": param_analysis.min_val,
                "max": param_analysis.max_val,
            },
            "actual_sharpe": actual_result.metrics.get("sharpe", 0),
            "report": report,
        }

        return ApiResponse(data=result_data)

    except Exception as e:
        return ApiResponse(code=500, message=f"Monte Carlo test failed: {str(e)}")
