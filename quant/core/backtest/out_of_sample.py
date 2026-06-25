"""样本外测试 - 训练/验证/测试集划分。

功能：
  - 将历史数据划分为训练集、验证集、测试集
  - 支持滚动窗口回测
  - 支持多时间段回测
  - 检测过拟合风险
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd

from quant.core.backtest.engine import BacktestEngine, BacktestRequest, BacktestResult
from quant.core.strategy.base import Strategy


@dataclass(frozen=True)
class TimePeriod:
    """时间段定义。"""
    name: str
    start_date: date
    end_date: date
    description: str = ""

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days

    @property
    def years(self) -> float:
        return self.days / 365.25


@dataclass(frozen=True)
class OutOfSampleResult:
    """样本外测试结果。"""
    period: TimePeriod
    result: BacktestResult
    is_train: bool  # True=训练集, False=验证集/测试集

    @property
    def metrics(self) -> dict[str, float]:
        return self.result.metrics


@dataclass(frozen=True)
class WalkForwardResult:
    """滚动窗口测试结果。"""
    window_id: int
    train_period: TimePeriod
    test_period: TimePeriod
    train_result: BacktestResult
    test_result: BacktestResult

    @property
    def train_metrics(self) -> dict[str, float]:
        return self.train_result.metrics

    @property
    def test_metrics(self) -> dict[str, float]:
        return self.test_result.metrics

    @property
    def overfit_score(self) -> float:
        """过拟合评分（0-1，越高越可能过拟合）。

        计算方法：比较训练集和测试集的夏普比率差异。
        如果测试集夏普远低于训练集，说明可能过拟合。
        """
        train_sharpe = self.train_metrics.get("sharpe", 0)
        test_sharpe = self.test_metrics.get("sharpe", 0)

        if train_sharpe <= 0:
            return 0.0

        # 计算夏普比率衰减
        decay = (train_sharpe - test_sharpe) / train_sharpe
        return max(0.0, min(1.0, decay))


class OutOfSampleTester:
    """样本外测试器。"""

    def __init__(self, engine: BacktestEngine | None = None):
        self.engine = engine or BacktestEngine()

    def split_periods(
        self,
        start_date: date,
        end_date: date,
        train_ratio: float = 0.6,
        val_ratio: float = 0.2,
        test_ratio: float = 0.2,
    ) -> tuple[TimePeriod, TimePeriod, TimePeriod]:
        """划分训练集、验证集、测试集。

        Args:
            start_date: 起始日期
            end_date: 结束日期
            train_ratio: 训练集比例
            val_ratio: 验证集比例
            test_ratio: 测试集比例

        Returns:
            (train_period, val_period, test_period)
        """
        total_days = (end_date - start_date).days
        train_days = int(total_days * train_ratio)
        val_days = int(total_days * val_ratio)

        train_end = start_date + timedelta(days=train_days)
        val_end = train_end + timedelta(days=val_days)

        train = TimePeriod(
            name="训练集",
            start_date=start_date,
            end_date=train_end,
            description="用于策略开发和参数调优",
        )
        val = TimePeriod(
            name="验证集",
            start_date=train_end + timedelta(days=1),
            end_date=val_end,
            description="用于验证策略参数",
        )
        test = TimePeriod(
            name="测试集",
            start_date=val_end + timedelta(days=1),
            end_date=end_date,
            description="用于最终评估策略表现",
        )

        return train, val, test

    def run_out_of_sample_test(
        self,
        strategy: Strategy,
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        benchmark_bars: pd.DataFrame | None = None,
        benchmark_code: str = "000300.SH",
        initial_cash: float = 1_000_000,
        rebalance: str = "weekly",
        train_ratio: float = 0.6,
        val_ratio: float = 0.2,
        test_ratio: float = 0.2,
    ) -> list[OutOfSampleResult]:
        """运行样本外测试。

        Args:
            strategy: 策略
            bars: 日线数据
            stocks: 股票信息
            benchmark_bars: 基准数据
            benchmark_code: 基准代码
            initial_cash: 初始资金
            rebalance: 再平衡频率
            train_ratio: 训练集比例
            val_ratio: 验证集比例
            test_ratio: 测试集比例

        Returns:
            样本外测试结果列表
        """
        # 获取数据范围
        start_date = bars["trade_date"].min()
        end_date = bars["trade_date"].max()

        # 划分时间段
        train, val, test = self.split_periods(
            start_date, end_date, train_ratio, val_ratio, test_ratio
        )

        results = []

        # 训练集回测
        train_bars = bars[
            (bars["trade_date"] >= train.start_date) & (bars["trade_date"] <= train.end_date)
        ]
        if not train_bars.empty:
            train_result = self.engine.run(BacktestRequest(
                bars=train_bars,
                stocks=stocks,
                strategy=strategy,
                benchmark_bars=benchmark_bars,
                benchmark_code=benchmark_code,
                initial_cash=initial_cash,
                rebalance=rebalance,
            ))
            results.append(OutOfSampleResult(
                period=train,
                result=train_result,
                is_train=True,
            ))

        # 验证集回测
        val_bars = bars[
            (bars["trade_date"] >= val.start_date) & (bars["trade_date"] <= val.end_date)
        ]
        if not val_bars.empty:
            val_result = self.engine.run(BacktestRequest(
                bars=val_bars,
                stocks=stocks,
                strategy=strategy,
                benchmark_bars=benchmark_bars,
                benchmark_code=benchmark_code,
                initial_cash=initial_cash,
                rebalance=rebalance,
            ))
            results.append(OutOfSampleResult(
                period=val,
                result=val_result,
                is_train=False,
            ))

        # 测试集回测
        test_bars = bars[
            (bars["trade_date"] >= test.start_date) & (bars["trade_date"] <= test.end_date)
        ]
        if not test_bars.empty:
            test_result = self.engine.run(BacktestRequest(
                bars=test_bars,
                stocks=stocks,
                strategy=strategy,
                benchmark_bars=benchmark_bars,
                benchmark_code=benchmark_code,
                initial_cash=initial_cash,
                rebalance=rebalance,
            ))
            results.append(OutOfSampleResult(
                period=test,
                result=test_result,
                is_train=False,
            ))

        return results

    def analyze_overfit_risk(
        self,
        results: list[OutOfSampleResult],
    ) -> dict[str, Any]:
        """分析过拟合风险。

        Args:
            results: 样本外测试结果

        Returns:
            过拟合风险分析结果
        """
        if len(results) < 2:
            return {"risk_level": "unknown", "message": "数据不足，无法分析"}

        train_result = next((r for r in results if r.is_train), None)
        test_results = [r for r in results if not r.is_train]

        if not train_result or not test_results:
            return {"risk_level": "unknown", "message": "数据不足，无法分析"}

        train_sharpe = train_result.metrics.get("sharpe", 0)
        test_sharpes = [r.metrics.get("sharpe", 0) for r in test_results]
        avg_test_sharpe = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0

        # 计算夏普比率衰减
        if train_sharpe > 0:
            decay = (train_sharpe - avg_test_sharpe) / train_sharpe
        else:
            decay = 0

        # 判断过拟合风险等级
        if decay < 0.2:
            risk_level = "low"
            message = "策略在样本外表现稳定，过拟合风险低"
        elif decay < 0.5:
            risk_level = "medium"
            message = "策略在样本外有一定衰减，建议进一步验证"
        else:
            risk_level = "high"
            message = "策略在样本外表现显著下降，可能存在过拟合"

        return {
            "risk_level": risk_level,
            "message": message,
            "train_sharpe": train_sharpe,
            "avg_test_sharpe": avg_test_sharpe,
            "sharpe_decay": decay,
            "train_metrics": train_result.metrics,
            "test_metrics": [r.metrics for r in test_results],
        }


class WalkForwardTester:
    """滚动窗口测试器。"""

    def __init__(self, engine: BacktestEngine | None = None):
        self.engine = engine or BacktestEngine()

    def run_walk_forward_test(
        self,
        strategy: Strategy,
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        benchmark_bars: pd.DataFrame | None = None,
        benchmark_code: str = "000300.SH",
        initial_cash: float = 1_000_000,
        rebalance: str = "weekly",
        train_days: int = 252,  # 1年
        test_days: int = 63,    # 1个季度
        step_days: int = 63,    # 滚动步长
    ) -> list[WalkForwardResult]:
        """运行滚动窗口测试。

        Args:
            strategy: 策略
            bars: 日线数据
            stocks: 股票信息
            benchmark_bars: 基准数据
            benchmark_code: 基准代码
            initial_cash: 初始资金
            rebalance: 再平衡频率
            train_days: 训练窗口天数
            test_days: 测试窗口天数
            step_days: 滚动步长天数

        Returns:
            滚动窗口测试结果列表
        """
        start_date = bars["trade_date"].min()
        end_date = bars["trade_date"].max()

        results = []
        window_id = 0

        current_start = start_date
        while True:
            train_end = current_start + timedelta(days=train_days)
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=test_days)

            if test_end > end_date:
                break

            train_period = TimePeriod(
                name=f"训练窗口 {window_id + 1}",
                start_date=current_start,
                end_date=train_end,
            )
            test_period = TimePeriod(
                name=f"测试窗口 {window_id + 1}",
                start_date=test_start,
                end_date=test_end,
            )

            # 训练集回测
            train_bars = bars[
                (bars["trade_date"] >= train_period.start_date) &
                (bars["trade_date"] <= train_period.end_date)
            ]
            train_result = self.engine.run(BacktestRequest(
                bars=train_bars,
                stocks=stocks,
                strategy=strategy,
                benchmark_bars=benchmark_bars,
                benchmark_code=benchmark_code,
                initial_cash=initial_cash,
                rebalance=rebalance,
            ))

            # 测试集回测
            test_bars = bars[
                (bars["trade_date"] >= test_period.start_date) &
                (bars["trade_date"] <= test_period.end_date)
            ]
            test_result = self.engine.run(BacktestRequest(
                bars=test_bars,
                stocks=stocks,
                strategy=strategy,
                benchmark_bars=benchmark_bars,
                benchmark_code=benchmark_code,
                initial_cash=initial_cash,
                rebalance=rebalance,
            ))

            results.append(WalkForwardResult(
                window_id=window_id,
                train_period=train_period,
                test_period=test_period,
                train_result=train_result,
                test_result=test_result,
            ))

            window_id += 1
            current_start += timedelta(days=step_days)

        return results

    def analyze_walk_forward_results(
        self,
        results: list[WalkForwardResult],
    ) -> dict[str, Any]:
        """分析滚动窗口测试结果。

        Args:
            results: 滚动窗口测试结果

        Returns:
            分析结果
        """
        if not results:
            return {"message": "无测试结果"}

        # 计算平均指标
        train_sharpes = [r.train_metrics.get("sharpe", 0) for r in results]
        test_sharpes = [r.test_metrics.get("sharpe", 0) for r in results]
        overfit_scores = [r.overfit_score for r in results]

        avg_train_sharpe = sum(train_sharpes) / len(train_sharpes)
        avg_test_sharpe = sum(test_sharpes) / len(test_sharpes)
        avg_overfit_score = sum(overfit_scores) / len(overfit_scores)

        # 计算一致性
        positive_test_windows = sum(1 for s in test_sharpes if s > 0)
        consistency = positive_test_windows / len(test_sharpes) if test_sharpes else 0

        # 判断稳定性
        if avg_overfit_score < 0.2 and consistency > 0.7:
            stability = "stable"
            message = "策略在不同时间段表现稳定"
        elif avg_overfit_score < 0.5 and consistency > 0.5:
            stability = "moderate"
            message = "策略表现有一定波动，建议进一步优化"
        else:
            stability = "unstable"
            message = "策略表现不稳定，可能存在过拟合"

        return {
            "stability": stability,
            "message": message,
            "avg_train_sharpe": avg_train_sharpe,
            "avg_test_sharpe": avg_test_sharpe,
            "avg_overfit_score": avg_overfit_score,
            "consistency": consistency,
            "window_count": len(results),
            "train_sharpes": train_sharpes,
            "test_sharpes": test_sharpes,
            "overfit_scores": overfit_scores,
        }
