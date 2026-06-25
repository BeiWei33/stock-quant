"""实验引擎 - 参数扫描、优化、实验记录。

支持的优化模式：
  - 网格搜索（Grid Search）：遍历参数组合
  - 随机搜索（Random Search）：随机采样 N 组参数
"""
from __future__ import annotations

import itertools
import json
import random
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .regime import MarketRegimeDetector
from .scoring import StrategyScorer

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "research_store" / "market_data.sqlite3"
EXPERIMENT_DB = ROOT / "research_store" / "experiments.sqlite3"


@dataclass
class ExperimentConfig:
    """实验配置。"""
    experiment_id: str
    name: str
    strategy_id: str
    param_grid: dict[str, list[Any]]
    metric: str = "sharpe"
    universe: str = "all"
    start_date: str = "2025-01-01"
    end_date: str = ""
    rebalance: str = "weekly"
    initial_cash: float = 1_000_000
    benchmark_code: str = "000300.SH"


@dataclass
class ExperimentRun:
    """单次实验运行结果。"""
    run_id: str
    experiment_id: str
    params: dict[str, Any]
    metrics: dict[str, Any]
    score: dict[str, Any] = field(default_factory=dict)
    rank: int = 0


@dataclass
class ExperimentResult:
    """实验结果。"""
    experiment_id: str
    name: str
    strategy_id: str
    method: str
    total_runs: int
    best_run: ExperimentRun | None
    runs: list[ExperimentRun]
    regime: str = ""
    created_at: str = ""


class ExperimentEngine:
    """实验引擎。"""

    def __init__(self):
        self.scorer = StrategyScorer()
        self.regime_detector = MarketRegimeDetector()
        self._init_db()

    def _init_db(self):
        """初始化实验数据库。"""
        if not EXPERIMENT_DB.exists():
            conn = sqlite3.connect(str(EXPERIMENT_DB))
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiment_runs (
                    run_id TEXT PRIMARY KEY,
                    experiment_id TEXT,
                    params TEXT,
                    metrics TEXT,
                    score TEXT,
                    rank INTEGER,
                    created_at TEXT,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                )
            """)
            conn.commit()
            conn.close()

    def run_grid_search(self, config: ExperimentConfig) -> ExperimentResult:
        """运行网格搜索。

        Args:
            config: 实验配置

        Returns:
            实验结果
        """
        from quant.core.backtest.engine import BacktestEngine, BacktestRequest
        from quant.core.strategy.factory import build_strategy
        from quant.core.persistence.sqlite_store import SqliteStore

        # 生成参数组合
        param_combinations = self._generate_grid_combinations(config.param_grid)

        # 限制最大组合数
        if len(param_combinations) > 100:
            param_combinations = param_combinations[:100]

        # 运行回测
        runs = self._run_backtests(config, param_combinations, "grid")

        # 排名
        runs = self._rank_runs(runs, config.metric)

        # 检测市场状态
        regime = self._detect_regime(config)

        # 构建结果
        result = ExperimentResult(
            experiment_id=config.experiment_id,
            name=config.name,
            strategy_id=config.strategy_id,
            method="grid",
            total_runs=len(runs),
            best_run=runs[0] if runs else None,
            runs=runs,
            regime=regime,
            created_at=datetime.now(UTC).isoformat(),
        )

        # 保存到数据库
        self._save_experiment(config, result)

        return result

    def run_random_search(
        self,
        config: ExperimentConfig,
        n_trials: int = 50,
    ) -> ExperimentResult:
        """运行随机搜索。

        Args:
            config: 实验配置
            n_trials: 随机采样次数

        Returns:
            实验结果
        """
        # 生成随机参数组合
        param_combinations = self._generate_random_combinations(
            config.param_grid, n_trials
        )

        # 运行回测
        runs = self._run_backtests(config, param_combinations, "random")

        # 排名
        runs = self._rank_runs(runs, config.metric)

        # 检测市场状态
        regime = self._detect_regime(config)

        # 构建结果
        result = ExperimentResult(
            experiment_id=config.experiment_id,
            name=config.name,
            strategy_id=config.strategy_id,
            method="random",
            total_runs=len(runs),
            best_run=runs[0] if runs else None,
            runs=runs,
            regime=regime,
            created_at=datetime.now(UTC).isoformat(),
        )

        # 保存到数据库
        self._save_experiment(config, result)

        return result

    def _run_backtests(
        self,
        config: ExperimentConfig,
        param_combinations: list[dict[str, Any]],
        method: str,
    ) -> list[ExperimentRun]:
        """运行多组回测。"""
        from quant.core.backtest.engine import BacktestEngine, BacktestRequest
        from quant.core.strategy.factory import build_strategy
        from quant.core.persistence.sqlite_store import SqliteStore
        from quant.core.factor.technical import FactorEngine, MomentumFactor

        store = SqliteStore(DB_PATH)
        bars = store.load_daily_bars(
            start_date=self._parse_date(config.start_date),
            end_date=self._parse_date(config.end_date),
        )
        stocks = store.load_stocks()
        benchmark_bars = store.load_benchmark_bars(config.benchmark_code)

        # 应用股票池过滤
        universe = getattr(config, 'universe', 'all') or 'all'
        if universe != 'all':
            bars = self._filter_by_universe(bars, universe)
            print(f"[Experiment] Filtered to {universe}: {bars['ts_code'].nunique()} stocks")

        runs = []
        for i, params in enumerate(param_combinations):
            try:
                # 构建策略
                strategy = build_strategy(config.strategy_id, **params)

                # 如果是自定义脚本策略，需要加载脚本代码
                if config.strategy_id in ("custom", "custom_script"):
                    from quant.core.strategy.script_adapter import load_script_from_db
                    script_code = load_script_from_db(config.experiment_id)
                    if script_code:
                        params["script_code"] = script_code
                        strategy = build_strategy(config.strategy_id, **params)

                # 构建因子引擎
                factors = strategy.required_factors()
                factor_engine = FactorEngine(factors) if factors else FactorEngine([MomentumFactor(60)])

                # 运行回测
                engine = BacktestEngine(factor_engine=factor_engine)
                result = engine.run(BacktestRequest(
                    bars=bars,
                    stocks=stocks,
                    strategy=strategy,
                    benchmark_bars=benchmark_bars,
                    benchmark_code=config.benchmark_code,
                    initial_cash=config.initial_cash,
                    rebalance=config.rebalance,
                ))

                # 构建运行结果
                run = ExperimentRun(
                    run_id=f"{config.experiment_id}_{i+1}",
                    experiment_id=config.experiment_id,
                    params=params,
                    metrics=result.metrics,
                )
                runs.append(run)

            except Exception as e:
                # 记录失败的运行
                run = ExperimentRun(
                    run_id=f"{config.experiment_id}_{i+1}",
                    experiment_id=config.experiment_id,
                    params=params,
                    metrics={"error": str(e)},
                )
                runs.append(run)

        return runs

    def _generate_grid_combinations(
        self, param_grid: dict[str, list[Any]]
    ) -> list[dict[str, Any]]:
        """生成网格搜索参数组合。"""
        keys = list(param_grid.keys())
        values = list(param_grid.values())

        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations

    def _generate_random_combinations(
        self, param_grid: dict[str, list[Any]], n_trials: int
    ) -> list[dict[str, Any]]:
        """生成随机搜索参数组合。"""
        combinations = []
        for _ in range(n_trials):
            params = {}
            for key, values in param_grid.items():
                params[key] = random.choice(values)
            combinations.append(params)

        return combinations

    def _rank_runs(
        self, runs: list[ExperimentRun], metric: str
    ) -> list[ExperimentRun]:
        """对运行结果排名。"""
        # 计算评分
        for run in runs:
            if "error" not in run.metrics:
                run.score = self.scorer.score(run.metrics)

        # 按指标排序
        def get_metric(run: ExperimentRun) -> float:
            if "error" in run.metrics:
                return float("-inf")
            return run.metrics.get(metric, 0)

        runs.sort(key=get_metric, reverse=True)

        # 设置排名
        for i, run in enumerate(runs):
            run.rank = i + 1

        return runs

    def _detect_regime(self, config: ExperimentConfig) -> str:
        """检测市场状态。"""
        try:
            from quant.core.persistence.sqlite_store import SqliteStore

            store = SqliteStore(DB_PATH)
            bars = store.load_daily_bars(
                start_date=self._parse_date(config.start_date),
                end_date=self._parse_date(config.end_date),
            )

            if bars.empty:
                return "unknown"

            result = self.regime_detector.detect(bars)
            return result.regime

        except Exception:
            return "unknown"

    def _save_experiment(
        self, config: ExperimentConfig, result: ExperimentResult
    ):
        """保存实验结果到数据库。"""
        conn = sqlite3.connect(str(EXPERIMENT_DB))
        try:
            # 保存实验配置
            conn.execute(
                """INSERT OR REPLACE INTO experiments
                   (experiment_id, name, strategy_id, param_grid, metric, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    config.experiment_id,
                    config.name,
                    config.strategy_id,
                    json.dumps(config.param_grid),
                    config.metric,
                    "completed",
                    result.created_at,
                ),
            )

            # 保存运行结果
            for run in result.runs:
                conn.execute(
                    """INSERT OR REPLACE INTO experiment_runs
                       (run_id, experiment_id, params, metrics, score, rank, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run.run_id,
                        run.experiment_id,
                        json.dumps(run.params),
                        json.dumps(run.metrics),
                        json.dumps(run.score),
                        run.rank,
                        result.created_at,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        """获取实验结果。"""
        conn = sqlite3.connect(str(EXPERIMENT_DB))
        conn.row_factory = sqlite3.Row
        try:
            # 获取实验配置
            row = conn.execute(
                "SELECT * FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()

            if not row:
                return None

            experiment = dict(row)
            experiment["param_grid"] = json.loads(experiment["param_grid"])

            # 获取运行结果
            rows = conn.execute(
                "SELECT * FROM experiment_runs WHERE experiment_id = ? ORDER BY rank",
                (experiment_id,),
            ).fetchall()

            experiment["runs"] = []
            for run_row in rows:
                run = dict(run_row)
                run["params"] = json.loads(run["params"])
                run["metrics"] = json.loads(run["metrics"])
                run["score"] = json.loads(run["score"])
                experiment["runs"].append(run)

            return experiment

        finally:
            conn.close()

    def list_experiments(self, limit: int = 20) -> list[dict[str, Any]]:
        """列出实验记录。"""
        conn = sqlite3.connect(str(EXPERIMENT_DB))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

            experiments = []
            for row in rows:
                exp = dict(row)
                exp["param_grid"] = json.loads(exp["param_grid"])
                experiments.append(exp)

            return experiments

        finally:
            conn.close()

    @staticmethod
    def _parse_date(value: str):
        """解析日期字符串。"""
        if not value:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _filter_by_universe(bars, universe: str):
        """按股票池过滤数据。"""
        import sqlite3

        if universe == 'all':
            return bars

        # 连接数据库查询分类
        db_path = Path("research_store/market_data.sqlite3")
        if not db_path.exists():
            print(f"[Warning] Database not found, using all stocks")
            return bars

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 解析股票池
        if "+" in universe:
            categories = universe.split("+")
            placeholders = ",".join(["?" for _ in categories])
            cursor.execute(f"SELECT ts_code FROM stocks WHERE industry IN ({placeholders})", categories)
        else:
            category_map = {
                "csi300": "CSI300",
                "csi500": "CSI500",
                "csi1000": "CSI1000",
                "sse50": "SSE50",
                "chinext": "ChiNext",
                "star50": "STAR50",
                "csi800": None,
            }

            category = category_map.get(universe)

            if universe == "csi800":
                cursor.execute("SELECT ts_code FROM stocks WHERE industry IN ('CSI300', 'CSI500')")
            elif category:
                cursor.execute("SELECT ts_code FROM stocks WHERE industry = ?", (category,))
            else:
                print(f"[Warning] Unknown universe: {universe}, using all stocks")
                conn.close()
                return bars

        valid_codes = set(row[0] for row in cursor.fetchall())
        conn.close()

        if not valid_codes:
            print(f"[Warning] No stock codes found for {universe}, using all stocks")
            return bars

        # 过滤数据
        filtered = bars[bars["ts_code"].isin(valid_codes)]
        return filtered.reset_index(drop=True)
