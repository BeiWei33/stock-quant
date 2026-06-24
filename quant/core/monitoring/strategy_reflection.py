"""策略反思引擎 - 定期回顾策略表现。

功能：
  - 验证历史决策是否正确
  - 生成反思报告
  - 参数敏感性分析
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class StrategyReflection:
    """策略反思报告。"""
    strategy_id: str
    period: str  # "7d" / "30d" / "90d"
    summary: str
    metrics_trend: dict[str, str]  # {"sharpe": "↑", "drawdown": "↓"}
    regime_context: str
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "period": self.period,
            "summary": self.summary,
            "metrics_trend": self.metrics_trend,
            "regime_context": self.regime_context,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "created_at": self.created_at,
        }


@dataclass
class SensitivityReport:
    """参数敏感性报告。"""
    param_name: str
    param_values: list[Any]
    metrics_by_value: dict[str, dict[str, float]]  # {value: {metric: value}}
    optimal_value: Any
    stability_range: tuple[Any, Any]
    conclusion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "param_name": self.param_name,
            "param_values": self.param_values,
            "metrics_by_value": self.metrics_by_value,
            "optimal_value": self.optimal_value,
            "stability_range": self.stability_range,
            "conclusion": self.conclusion,
        }


class StrategyReflectionEngine:
    """策略反思引擎。"""

    def __init__(self):
        pass

    def reflect(
        self,
        strategy_id: str,
        lookback_days: int = 30,
        backtest_results: list[dict[str, Any]] | None = None,
    ) -> StrategyReflection:
        """分析策略表现，生成反思报告。

        Args:
            strategy_id: 策略 ID
            lookback_days: 回看天数
            backtest_results: 历史回测结果

        Returns:
            反思报告
        """
        # 确定周期
        if lookback_days <= 7:
            period = "7d"
        elif lookback_days <= 30:
            period = "30d"
        else:
            period = "90d"

        # 分析指标趋势
        metrics_trend = self._analyze_trends(backtest_results)

        # 生成警告
        warnings = self._generate_warnings(backtest_results, metrics_trend)

        # 生成建议
        recommendations = self._generate_recommendations(metrics_trend, warnings)

        # 生成摘要
        summary = self._generate_summary(strategy_id, period, metrics_trend, warnings)

        # 市场状态
        regime_context = self._detect_regime_context(backtest_results)

        return StrategyReflection(
            strategy_id=strategy_id,
            period=period,
            summary=summary,
            metrics_trend=metrics_trend,
            regime_context=regime_context,
            warnings=warnings,
            recommendations=recommendations,
            created_at=datetime.now(UTC).isoformat(),
        )

    def _analyze_trends(
        self, results: list[dict[str, Any]] | None
    ) -> dict[str, str]:
        """分析指标趋势。"""
        if not results or len(results) < 2:
            return {
                "sharpe": "→",
                "annual_return": "→",
                "max_drawdown": "→",
                "win_rate": "→",
            }

        # 取最近两次结果
        recent = results[-1].get("metrics", {})
        previous = results[-2].get("metrics", {})

        trends = {}
        for metric in ["sharpe", "annual_return", "max_drawdown", "win_rate"]:
            curr = recent.get(metric, 0)
            prev = previous.get(metric, 0)

            if metric == "max_drawdown":
                # 回撤越小越好
                if curr < prev * 0.9:
                    trends[metric] = "↑"  # 回撤减小是好事
                elif curr > prev * 1.1:
                    trends[metric] = "↓"  # 回撤增大是坏事
                else:
                    trends[metric] = "→"
            else:
                if curr > prev * 1.1:
                    trends[metric] = "↑"
                elif curr < prev * 0.9:
                    trends[metric] = "↓"
                else:
                    trends[metric] = "→"

        return trends

    def _generate_warnings(
        self,
        results: list[dict[str, Any]] | None,
        trends: dict[str, str],
    ) -> list[str]:
        """生成警告。"""
        warnings = []

        if not results:
            return warnings

        latest = results[-1].get("metrics", {})

        # 夏普比率过低
        sharpe = latest.get("sharpe", 0)
        if sharpe < 0.5:
            warnings.append(f"夏普比率过低：{sharpe:.2f}（建议 > 0.8）")

        # 最大回撤过大
        max_dd = abs(latest.get("max_drawdown", 0))
        if max_dd > 20:
            warnings.append(f"最大回撤过大：{max_dd:.1f}%（建议 < 20%）")

        # 胜率过低
        win_rate = latest.get("win_rate", 0)
        if win_rate < 40:
            warnings.append(f"胜率过低：{win_rate:.1f}%（建议 > 50%）")

        # 趋势下降
        if trends.get("sharpe") == "↓":
            warnings.append("夏普比率呈下降趋势")
        if trends.get("annual_return") == "↓":
            warnings.append("年化收益呈下降趋势")

        return warnings

    def _generate_recommendations(
        self,
        trends: dict[str, str],
        warnings: list[str],
    ) -> list[str]:
        """生成建议。"""
        recommendations = []

        if not warnings:
            recommendations.append("策略表现良好，继续保持")
            return recommendations

        # 根据警告生成建议
        for warning in warnings:
            if "夏普比率" in warning:
                recommendations.append("考虑调整因子参数或增加趋势过滤")
            elif "回撤" in warning:
                recommendations.append("考虑降低仓位或增加止损机制")
            elif "胜率" in warning:
                recommendations.append("考虑调整入场条件或增加过滤器")

        # 根据趋势生成建议
        if trends.get("sharpe") == "↓":
            recommendations.append("策略可能过拟合，建议进行样本外测试")

        return recommendations

    def _generate_summary(
        self,
        strategy_id: str,
        period: str,
        trends: dict[str, str],
        warnings: list[str],
    ) -> str:
        """生成摘要。"""
        # 趋势描述
        trend_desc = []
        if trends.get("sharpe") == "↑":
            trend_desc.append("夏普比率提升")
        elif trends.get("sharpe") == "↓":
            trend_desc.append("夏普比率下降")

        if trends.get("annual_return") == "↑":
            trend_desc.append("收益提升")
        elif trends.get("annual_return") == "↓":
            trend_desc.append("收益下降")

        trend_str = "，".join(trend_desc) if trend_desc else "表现稳定"

        # 警告描述
        warning_str = f"，有 {len(warnings)} 个警告" if warnings else ""

        return f"策略 {strategy_id} 在 {period} 周期内{trend_str}{warning_str}"

    def _detect_regime_context(
        self, results: list[dict[str, Any]] | None
    ) -> str:
        """检测市场状态。"""
        if not results:
            return "数据不足，无法判断市场状态"

        latest = results[-1].get("metrics", {})
        total_return = latest.get("total_return", 0)
        max_dd = abs(latest.get("max_drawdown", 0))

        if total_return > 10 and max_dd < 10:
            return "近期市场处于牛市趋势"
        elif total_return < -10:
            return "近期市场处于熊市趋势"
        elif max_dd > 20:
            return "近期市场波动较大"
        else:
            return "近期市场处于震荡状态"

    def generate_weekly_report(
        self,
        strategies: list[dict[str, Any]],
    ) -> str:
        """生成周度反思汇总 Markdown。"""
        lines = ["# 策略周度反思报告", ""]
        lines.append(f"生成时间：{datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        for strategy_data in strategies:
            strategy_id = strategy_data.get("strategy_id", "unknown")
            results = strategy_data.get("results", [])

            reflection = self.reflect(
                strategy_id=strategy_id,
                lookback_days=7,
                backtest_results=results,
            )

            lines.append(f"## {strategy_id}")
            lines.append("")
            lines.append(f"**摘要**：{reflection.summary}")
            lines.append("")

            # 指标趋势
            lines.append("**指标趋势**：")
            for metric, trend in reflection.metrics_trend.items():
                lines.append(f"- {metric}: {trend}")
            lines.append("")

            # 警告
            if reflection.warnings:
                lines.append("**警告**：")
                for warning in reflection.warnings:
                    lines.append(f"- ⚠️ {warning}")
                lines.append("")

            # 建议
            if reflection.recommendations:
                lines.append("**建议**：")
                for rec in reflection.recommendations:
                    lines.append(f"- 💡 {rec}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)


class ParameterSensitivityAnalyzer:
    """参数敏感性分析器。"""

    def __init__(self):
        pass

    def analyze(
        self,
        strategy_name: str,
        param_name: str,
        param_values: list[Any],
        backtest_results: list[dict[str, Any]],
    ) -> SensitivityReport:
        """分析参数敏感性。

        Args:
            strategy_name: 策略名称
            param_name: 参数名称
            param_values: 参数值列表
            backtest_results: 对应的回测结果

        Returns:
            敏感性报告
        """
        # 提取指标
        metrics_by_value = {}
        for value, result in zip(param_values, backtest_results):
            metrics = result.get("metrics", {})
            metrics_by_value[str(value)] = {
                "sharpe": metrics.get("sharpe", 0),
                "annual_return": metrics.get("annual_return", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
            }

        # 找到最优值
        best_value = max(
            param_values,
            key=lambda v: metrics_by_value.get(str(v), {}).get("sharpe", 0),
        )

        # 计算稳定区间
        stability_range = self._find_stability_range(
            param_values, metrics_by_value
        )

        # 生成结论
        conclusion = self._generate_conclusion(
            param_name, param_values, metrics_by_value, best_value, stability_range
        )

        return SensitivityReport(
            param_name=param_name,
            param_values=param_values,
            metrics_by_value=metrics_by_value,
            optimal_value=best_value,
            stability_range=stability_range,
            conclusion=conclusion,
        )

    def _find_stability_range(
        self,
        param_values: list[Any],
        metrics_by_value: dict[str, dict[str, float]],
    ) -> tuple[Any, Any]:
        """找到参数的稳定区间。"""
        # 找到夏普比率 > 80% 最优值的区间
        sharpes = [
            metrics_by_value.get(str(v), {}).get("sharpe", 0)
            for v in param_values
        ]
        max_sharpe = max(sharpes) if sharpes else 0
        threshold = max_sharpe * 0.8

        stable_values = [
            v for v, s in zip(param_values, sharpes)
            if s >= threshold
        ]

        if stable_values:
            return (min(stable_values), max(stable_values))
        return (param_values[0], param_values[-1])

    def _generate_conclusion(
        self,
        param_name: str,
        param_values: list[Any],
        metrics_by_value: dict[str, dict[str, float]],
        best_value: Any,
        stability_range: tuple[Any, Any],
    ) -> str:
        """生成结论。"""
        # 计算变异系数
        sharpes = [
            metrics_by_value.get(str(v), {}).get("sharpe", 0)
            for v in param_values
        ]

        if not sharpes or max(sharpes) <= 0:
            return f"{param_name} 对策略影响较小"

        mean_sharpe = sum(sharpes) / len(sharpes)
        std_sharpe = (sum((s - mean_sharpe) ** 2 for s in sharpes) / len(sharpes)) ** 0.5
        cv = std_sharpe / mean_sharpe if mean_sharpe > 0 else 0

        if cv < 0.1:
            stability = "非常稳定"
        elif cv < 0.2:
            stability = "较稳定"
        else:
            stability = "敏感"

        return (
            f"{param_name} 在 [{stability_range[0]}, {stability_range[1]}] 区间内表现稳定，"
            f"最优值为 {best_value}，参数敏感性{stability}（CV={cv:.2f}）"
        )
