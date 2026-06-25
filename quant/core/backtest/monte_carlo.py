"""蒙特卡洛测试 - 通过随机模拟评估策略稳健性。

功能：
  - 随机打乱交易顺序
  - 随机抽样股票池
  - 随机调整参数
  - 计算策略表现的置信区间
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from quant.core.backtest.engine import BacktestEngine, BacktestRequest, BacktestResult
from quant.core.strategy.base import Strategy


@dataclass(frozen=True)
class MonteCarloResult:
    """蒙特卡洛测试结果。"""
    simulation_id: int
    metrics: dict[str, float]
    seed: int


@dataclass(frozen=True)
class MonteCarloAnalysis:
    """蒙特卡洛分析结果。"""
    n_simulations: int
    metric_name: str
    mean: float
    std: float
    min_val: float
    max_val: float
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    confidence_interval_95: tuple[float, float]


class MonteCarloTester:
    """蒙特卡洛测试器。"""

    def __init__(self, engine: BacktestEngine | None = None):
        self.engine = engine or BacktestEngine()

    def run_bootstrap_test(
        self,
        strategy: Strategy,
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        benchmark_bars: pd.DataFrame | None = None,
        benchmark_code: str = "000300.SH",
        initial_cash: float = 1_000_000,
        rebalance: str = "weekly",
        n_simulations: int = 100,
        sample_ratio: float = 0.8,
    ) -> list[MonteCarloResult]:
        """运行 Bootstrap 测试。

        随机抽样股票池，测试策略在不同股票组合下的表现。

        Args:
            strategy: 策略
            bars: 日线数据
            stocks: 股票信息
            benchmark_bars: 基准数据
            benchmark_code: 基准代码
            initial_cash: 初始资金
            rebalance: 再平衡频率
            n_simulations: 模拟次数
            sample_ratio: 抽样比例

        Returns:
            蒙特卡洛测试结果列表
        """
        results = []

        # 获取所有股票代码
        all_stocks = stocks["ts_code"].unique()
        n_sample = int(len(all_stocks) * sample_ratio)

        for i in range(n_simulations):
            # 随机抽样股票
            seed = random.randint(0, 2**31)
            np.random.seed(seed)
            sampled_stocks = np.random.choice(all_stocks, size=n_sample, replace=False)

            # 过滤数据
            sampled_bars = bars[bars["ts_code"].isin(sampled_stocks)]
            sampled_stock_info = stocks[stocks["ts_code"].isin(sampled_stocks)]

            if sampled_bars.empty:
                continue

            # 运行回测
            try:
                result = self.engine.run(BacktestRequest(
                    bars=sampled_bars,
                    stocks=sampled_stock_info,
                    strategy=strategy,
                    benchmark_bars=benchmark_bars,
                    benchmark_code=benchmark_code,
                    initial_cash=initial_cash,
                    rebalance=rebalance,
                ))

                results.append(MonteCarloResult(
                    simulation_id=i,
                    metrics=result.metrics,
                    seed=seed,
                ))
            except Exception as e:
                # 跳过失败的模拟
                continue

        return results

    def run_parameter_perturbation_test(
        self,
        strategy_class: type,
        base_params: dict[str, Any],
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        benchmark_bars: pd.DataFrame | None = None,
        benchmark_code: str = "000300.SH",
        initial_cash: float = 1_000_000,
        rebalance: str = "weekly",
        n_simulations: int = 100,
        perturbation_range: float = 0.2,
    ) -> list[MonteCarloResult]:
        """运行参数扰动测试。

        随机调整策略参数，测试策略对参数的敏感性。

        Args:
            strategy_class: 策略类
            base_params: 基础参数
            bars: 日线数据
            stocks: 股票信息
            benchmark_bars: 基准数据
            benchmark_code: 基准代码
            initial_cash: 初始资金
            rebalance: 再平衡频率
            n_simulations: 模拟次数
            perturbation_range: 扰动范围（0.2 表示 ±20%）

        Returns:
            蒙特卡洛测试结果列表
        """
        results = []

        for i in range(n_simulations):
            seed = random.randint(0, 2**31)
            np.random.seed(seed)

            # 扰动参数
            perturbed_params = {}
            for key, value in base_params.items():
                if isinstance(value, (int, float)):
                    # 数值参数：随机扰动
                    perturbation = np.random.uniform(-perturbation_range, perturbation_range)
                    new_value = value * (1 + perturbation)

                    # 整数参数保持整数
                    if isinstance(value, int):
                        new_value = max(1, int(round(new_value)))
                    else:
                        new_value = max(0.0, new_value)

                    perturbed_params[key] = new_value
                else:
                    # 非数值参数：保持不变
                    perturbed_params[key] = value

            # 创建策略实例
            try:
                strategy = strategy_class(**perturbed_params)
            except Exception:
                continue

            # 运行回测
            try:
                result = self.engine.run(BacktestRequest(
                    bars=bars,
                    stocks=stocks,
                    strategy=strategy,
                    benchmark_bars=benchmark_bars,
                    benchmark_code=benchmark_code,
                    initial_cash=initial_cash,
                    rebalance=rebalance,
                ))

                results.append(MonteCarloResult(
                    simulation_id=i,
                    metrics=result.metrics,
                    seed=seed,
                ))
            except Exception:
                continue

        return results

    def analyze_results(
        self,
        results: list[MonteCarloResult],
        metric_name: str = "sharpe",
    ) -> MonteCarloAnalysis:
        """分析蒙特卡洛测试结果。

        Args:
            results: 蒙特卡洛测试结果
            metric_name: 分析的指标名称

        Returns:
            蒙特卡洛分析结果
        """
        values = [r.metrics.get(metric_name, 0) for r in results]
        values_array = np.array(values)

        # 计算统计量
        mean = float(np.mean(values_array))
        std = float(np.std(values_array))
        min_val = float(np.min(values_array))
        max_val = float(np.max(values_array))

        # 计算百分位数
        percentile_5 = float(np.percentile(values_array, 5))
        percentile_25 = float(np.percentile(values_array, 25))
        percentile_50 = float(np.percentile(values_array, 50))
        percentile_75 = float(np.percentile(values_array, 75))
        percentile_95 = float(np.percentile(values_array, 95))

        # 计算 95% 置信区间
        confidence_interval_95 = (percentile_5, percentile_95)

        return MonteCarloAnalysis(
            n_simulations=len(results),
            metric_name=metric_name,
            mean=mean,
            std=std,
            min_val=min_val,
            max_val=max_val,
            percentile_5=percentile_5,
            percentile_25=percentile_25,
            percentile_50=percentile_50,
            percentile_75=percentile_75,
            percentile_95=percentile_95,
            confidence_interval_95=confidence_interval_95,
        )

    def generate_report(
        self,
        bootstrap_results: list[MonteCarloResult],
        parameter_results: list[MonteCarloResult],
        actual_metrics: dict[str, float],
    ) -> str:
        """生成蒙特卡洛测试报告。

        Args:
            bootstrap_results: Bootstrap 测试结果
            parameter_results: 参数扰动测试结果
            actual_metrics: 实际策略指标

        Returns:
            Markdown 格式的报告
        """
        report = []
        report.append("# 蒙特卡洛测试报告\n")

        # Bootstrap 测试结果
        if bootstrap_results:
            report.append("## Bootstrap 测试（股票池抽样）\n")
            bootstrap_analysis = self.analyze_results(bootstrap_results, "sharpe")
            report.append(f"模拟次数: {bootstrap_analysis.n_simulations}\n")
            report.append("| 统计量 | 夏普比率 |")
            report.append("|--------|----------|")
            report.append(f"| 实际值 | {actual_metrics.get('sharpe', 0):.4f} |")
            report.append(f"| 均值 | {bootstrap_analysis.mean:.4f} |")
            report.append(f"| 标准差 | {bootstrap_analysis.std:.4f} |")
            report.append(f"| 5%分位 | {bootstrap_analysis.percentile_5:.4f} |")
            report.append(f"| 50%分位 | {bootstrap_analysis.percentile_50:.4f} |")
            report.append(f"| 95%分位 | {bootstrap_analysis.percentile_95:.4f} |")
            report.append(f"| 95%置信区间 | [{bootstrap_analysis.confidence_interval_95[0]:.4f}, {bootstrap_analysis.confidence_interval_95[1]:.4f}] |")
            report.append("")

            # 判断策略稳健性
            actual_sharpe = actual_metrics.get("sharpe", 0)
            if actual_sharpe > bootstrap_analysis.percentile_75:
                report.append("✅ 策略表现优于 75% 的随机组合，稳健性良好")
            elif actual_sharpe > bootstrap_analysis.percentile_50:
                report.append("⚠️ 策略表现处于中等水平，稳健性一般")
            else:
                report.append("❌ 策略表现低于 50% 的随机组合，稳健性较差")
            report.append("")

        # 参数扰动测试结果
        if parameter_results:
            report.append("## 参数扰动测试\n")
            param_analysis = self.analyze_results(parameter_results, "sharpe")
            report.append(f"模拟次数: {param_analysis.n_simulations}\n")
            report.append("| 统计量 | 夏普比率 |")
            report.append("|--------|----------|")
            report.append(f"| 实际值 | {actual_metrics.get('sharpe', 0):.4f} |")
            report.append(f"| 均值 | {param_analysis.mean:.4f} |")
            report.append(f"| 标准差 | {param_analysis.std:.4f} |")
            report.append(f"| 最小值 | {param_analysis.min_val:.4f} |")
            report.append(f"| 最大值 | {param_analysis.max_val:.4f} |")
            report.append("")

            # 判断参数敏感性
            if param_analysis.std < 0.1:
                report.append("✅ 策略对参数不敏感，参数鲁棒性良好")
            elif param_analysis.std < 0.3:
                report.append("⚠️ 策略对参数有一定敏感性，建议谨慎调参")
            else:
                report.append("❌ 策略对参数高度敏感，可能存在过拟合风险")
            report.append("")

        # 总结
        report.append("## 总结\n")
        if bootstrap_results and parameter_results:
            bootstrap_analysis = self.analyze_results(bootstrap_results, "sharpe")
            param_analysis = self.analyze_results(parameter_results, "sharpe")

            overall_score = 0
            if actual_metrics.get("sharpe", 0) > bootstrap_analysis.percentile_50:
                overall_score += 1
            if param_analysis.std < 0.2:
                overall_score += 1

            if overall_score == 2:
                report.append("🎯 **策略整体评价：优秀** - 稳健性和参数鲁棒性都良好")
            elif overall_score == 1:
                report.append("⚠️ **策略整体评价：一般** - 需要进一步优化")
            else:
                report.append("❌ **策略整体评价：较差** - 建议重新设计策略")

        return "\n".join(report)
