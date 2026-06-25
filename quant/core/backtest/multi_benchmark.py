"""多基准对比 - 同时对比多个基准的表现。

功能：
  - 同时对比沪深300、中证500、等权全市场等基准
  - 计算相对每个基准的超额收益和信息比率
  - 生成对比报告
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from quant.core.backtest.engine import BacktestEngine, BacktestRequest, BacktestResult
from quant.core.strategy.base import Strategy


@dataclass(frozen=True)
class BenchmarkComparison:
    """单个基准对比结果。"""
    benchmark_code: str
    benchmark_name: str
    strategy_metrics: dict[str, float]
    benchmark_metrics: dict[str, float]
    excess_return: float
    information_ratio: float
    tracking_error: float
    beta: float
    correlation: float


@dataclass(frozen=True)
class MultiBenchmarkResult:
    """多基准对比结果。"""
    strategy_name: str
    strategy_metrics: dict[str, float]
    comparisons: list[BenchmarkComparison]
    best_benchmark: str  # 超额收益最高的基准


class MultiBenchmarkTester:
    """多基准对比测试器。"""

    # 常用基准代码和名称
    BENCHMARKS = {
        "000300.SH": "沪深300",
        "000905.SH": "中证500",
        "equal_weight": "等权全市场",
    }

    def __init__(self, engine: BacktestEngine | None = None):
        self.engine = engine or BacktestEngine()

    def run_multi_benchmark_test(
        self,
        strategy: Strategy,
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        benchmark_bars_dict: dict[str, pd.DataFrame],
        initial_cash: float = 1_000_000,
        rebalance: str = "weekly",
        strategy_name: str = "策略",
    ) -> MultiBenchmarkResult:
        """运行多基准对比测试。

        Args:
            strategy: 策略
            bars: 日线数据
            stocks: 股票信息
            benchmark_bars_dict: 基准数据字典 {benchmark_code: benchmark_bars}
            initial_cash: 初始资金
            rebalance: 再平衡频率
            strategy_name: 策略名称

        Returns:
            多基准对比结果
        """
        comparisons = []

        # 运行策略回测（使用第一个基准作为主基准）
        first_benchmark_code = list(benchmark_bars_dict.keys())[0]
        first_benchmark_bars = benchmark_bars_dict[first_benchmark_code]

        strategy_result = self.engine.run(BacktestRequest(
            bars=bars,
            stocks=stocks,
            strategy=strategy,
            benchmark_bars=first_benchmark_bars,
            benchmark_code=first_benchmark_code,
            initial_cash=initial_cash,
            rebalance=rebalance,
        ))

        strategy_metrics = strategy_result.metrics

        # 对比每个基准
        for benchmark_code, benchmark_bars in benchmark_bars_dict.items():
            # 重新运行回测以获取与该基准的对比指标
            result = self.engine.run(BacktestRequest(
                bars=bars,
                stocks=stocks,
                strategy=strategy,
                benchmark_bars=benchmark_bars,
                benchmark_code=benchmark_code,
                initial_cash=initial_cash,
                rebalance=rebalance,
            ))

            benchmark_name = self.BENCHMARKS.get(benchmark_code, benchmark_code)

            comparisons.append(BenchmarkComparison(
                benchmark_code=benchmark_code,
                benchmark_name=benchmark_name,
                strategy_metrics=result.metrics,
                benchmark_metrics={
                    "total_return": result.metrics.get("benchmark_total_return", 0),
                    "annual_return": result.metrics.get("benchmark_annual_return", 0),
                    "volatility": result.metrics.get("benchmark_volatility", 0),
                },
                excess_return=result.metrics.get("excess_return", 0),
                information_ratio=result.metrics.get("information_ratio", 0),
                tracking_error=result.metrics.get("tracking_error", 0),
                beta=result.metrics.get("beta", 0),
                correlation=result.metrics.get("benchmark_correlation", 0),
            ))

        # 找出超额收益最高的基准
        best_benchmark = max(comparisons, key=lambda c: c.excess_return)

        return MultiBenchmarkResult(
            strategy_name=strategy_name,
            strategy_metrics=strategy_metrics,
            comparisons=comparisons,
            best_benchmark=best_benchmark.benchmark_name,
        )

    def generate_comparison_report(
        self,
        result: MultiBenchmarkResult,
    ) -> str:
        """生成对比报告。

        Args:
            result: 多基准对比结果

        Returns:
            Markdown 格式的报告
        """
        report = []
        report.append(f"# {result.strategy_name} - 多基准对比报告\n")

        # 策略表现
        report.append("## 策略表现\n")
        report.append(f"| 指标 | 值 |")
        report.append(f"|------|-----|")
        report.append(f"| 总收益 | {result.strategy_metrics.get('total_return', 0) * 100:.2f}% |")
        report.append(f"| 年化收益 | {result.strategy_metrics.get('annual_return', 0) * 100:.2f}% |")
        report.append(f"| 夏普比率 | {result.strategy_metrics.get('sharpe', 0):.4f} |")
        report.append(f"| 最大回撤 | {result.strategy_metrics.get('max_drawdown', 0) * 100:.2f}% |")
        report.append("")

        # 基准对比
        report.append("## 基准对比\n")
        report.append("| 基准 | 超额收益 | 信息比率 | 跟踪误差 | Beta | 相关系数 |")
        report.append("|------|----------|----------|----------|------|----------|")

        for comp in result.comparisons:
            report.append(
                f"| {comp.benchmark_name} "
                f"| {comp.excess_return * 100:.2f}% "
                f"| {comp.information_ratio:.4f} "
                f"| {comp.tracking_error * 100:.2f}% "
                f"| {comp.beta:.4f} "
                f"| {comp.correlation:.4f} |"
            )
        report.append("")

        # 结论
        report.append("## 结论\n")
        report.append(f"- 最佳基准：{result.best_benchmark}")
        best_comp = next(c for c in result.comparisons if c.benchmark_name == result.best_benchmark)
        report.append(f"- 超额收益：{best_comp.excess_return * 100:.2f}%")
        report.append(f"- 信息比率：{best_comp.information_ratio:.4f}")

        # 策略评价
        report.append("\n## 策略评价\n")
        if best_comp.excess_return > 0:
            report.append("✅ 策略跑赢基准，具有正超额收益")
        else:
            report.append("❌ 策略跑输基准，超额收益为负")

        if best_comp.information_ratio > 0.5:
            report.append("✅ 信息比率良好，超额收益稳定")
        elif best_comp.information_ratio > 0:
            report.append("⚠️ 信息比率较低，超额收益不稳定")
        else:
            report.append("❌ 信息比率为负，策略表现不佳")

        return "\n".join(report)

    def analyze_benchmark_sensitivity(
        self,
        result: MultiBenchmarkResult,
    ) -> dict[str, Any]:
        """分析基准敏感性。

        检查策略对不同基准的相对表现是否一致。

        Args:
            result: 多基准对比结果

        Returns:
            敏感性分析结果
        """
        excess_returns = [c.excess_return for c in result.comparisons]
        information_ratios = [c.information_ratio for c in result.comparisons]

        # 计算超额收益的标准差
        excess_return_std = pd.Series(excess_returns).std()
        avg_excess_return = sum(excess_returns) / len(excess_returns)
        avg_information_ratio = sum(information_ratios) / len(information_ratios)

        # 判断一致性
        if excess_return_std < 0.05:  # 5% 以内
            consistency = "high"
            message = "策略对不同基准的相对表现一致"
        elif excess_return_std < 0.10:  # 10% 以内
            consistency = "medium"
            message = "策略对不同基准的相对表现有一定差异"
        else:
            consistency = "low"
            message = "策略对不同基准的相对表现差异较大"

        return {
            "consistency": consistency,
            "message": message,
            "excess_return_std": excess_return_std,
            "avg_excess_return": avg_excess_return,
            "avg_information_ratio": avg_information_ratio,
            "excess_returns": excess_returns,
            "information_ratios": information_ratios,
        }
