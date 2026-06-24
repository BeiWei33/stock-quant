"""策略评分系统 - 多维度加权评分。

评分维度：
  - return: 总收益
  - annual_return: 年化收益
  - sharpe: 夏普比率
  - max_drawdown: 最大回撤（越小越好）
  - win_rate: 胜率
  - stability: 净值曲线稳定性
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScoringWeights:
    """评分权重配置。"""
    return_score: float = 0.20
    annual_return: float = 0.15
    sharpe: float = 0.20
    max_drawdown: float = 0.20
    win_rate: float = 0.10
    stability: float = 0.15


# 不同市场状态的权重配置
REGIME_WEIGHTS = {
    "bull_trend": ScoringWeights(
        return_score=0.30, annual_return=0.20, sharpe=0.15,
        max_drawdown=0.15, win_rate=0.10, stability=0.10,
    ),
    "bear_trend": ScoringWeights(
        return_score=0.15, annual_return=0.10, sharpe=0.20,
        max_drawdown=0.30, win_rate=0.10, stability=0.15,
    ),
    "range_compression": ScoringWeights(
        return_score=0.10, annual_return=0.10, sharpe=0.15,
        max_drawdown=0.15, win_rate=0.25, stability=0.25,
    ),
    "high_volatility": ScoringWeights(
        return_score=0.15, annual_return=0.10, sharpe=0.15,
        max_drawdown=0.30, win_rate=0.10, stability=0.20,
    ),
}


class StrategyScorer:
    """策略评分器。"""

    def __init__(self, weights: ScoringWeights | None = None):
        self.weights = weights or ScoringWeights()

    def score(self, metrics: dict[str, Any], regime: str = "") -> dict[str, Any]:
        """计算策略综合得分。

        Args:
            metrics: 回测指标
            regime: 市场状态（bull_trend, bear_trend, range_compression, high_volatility）

        Returns:
            评分结果，包含总分和各维度得分
        """
        # 根据市场状态选择权重
        weights = REGIME_WEIGHTS.get(regime, self.weights) if regime else self.weights

        # 计算各维度得分（0-100）
        scores = {
            "return_score": self._score_return(metrics.get("total_return", 0)),
            "annual_return": self._score_annual_return(metrics.get("annual_return", 0)),
            "sharpe": self._score_sharpe(metrics.get("sharpe", 0)),
            "max_drawdown": self._score_drawdown(metrics.get("max_drawdown", 0)),
            "win_rate": self._score_win_rate(metrics.get("win_rate", 0)),
            "stability": self._score_stability(metrics.get("equity_curve", [])),
        }

        # 加权总分
        total = sum(scores[k] * getattr(weights, k) for k in scores)

        return {
            "total_score": round(total, 2),
            "scores": {k: round(v, 2) for k, v in scores.items()},
            "weights": {
                k: round(getattr(weights, k), 2)
                for k in ["return_score", "annual_return", "sharpe", "max_drawdown", "win_rate", "stability"]
            },
            "regime": regime,
            "grade": self._grade(total),
        }

    def rank(self, results: list[dict[str, Any]], regime: str = "") -> list[dict[str, Any]]:
        """对多个回测结果排名。

        Args:
            results: 回测结果列表
            regime: 市场状态

        Returns:
            按总分排序的结果列表
        """
        scored = []
        for result in results:
            metrics = result.get("metrics", {})
            score_result = self.score(metrics, regime)
            scored.append({**result, "score": score_result})

        return sorted(scored, key=lambda x: x["score"]["total_score"], reverse=True)

    def _score_return(self, value: float) -> float:
        """总收益得分（-20% ~ 80%）。"""
        return self._bounded_score(value, floor=-20.0, ceiling=80.0)

    def _score_annual_return(self, value: float) -> float:
        """年化收益得分（-20% ~ 120%）。"""
        return self._bounded_score(value, floor=-20.0, ceiling=120.0)

    def _score_sharpe(self, value: float) -> float:
        """夏普比率得分（-1.0 ~ 3.0）。"""
        return self._bounded_score(value, floor=-1.0, ceiling=3.0)

    def _score_drawdown(self, value: float) -> float:
        """最大回撤得分（越小越好，5% ~ 45%）。"""
        value = abs(value)
        return self._inverse_score(value, floor=5.0, ceiling=45.0)

    def _score_win_rate(self, value: float) -> float:
        """胜率得分（35% ~ 70%）。"""
        return self._bounded_score(value, floor=35.0, ceiling=70.0)

    def _score_stability(self, equity_curve: list) -> float:
        """净值曲线稳定性得分。"""
        if not equity_curve or len(equity_curve) < 10:
            return 50.0

        # 计算净值曲线的变异系数
        values = [p.get("equity", p.get("total_asset", 0)) for p in equity_curve]
        if not values or min(values) <= 0:
            return 50.0

        mean = sum(values) / len(values)
        if mean <= 0:
            return 50.0

        variance = sum((v - mean) ** 2 for v in values) / len(values)
        cv = (variance ** 0.5) / mean

        # 变异系数越小，稳定性越高
        return self._inverse_score(cv * 100, floor=5.0, ceiling=30.0)

    @staticmethod
    def _bounded_score(value: float, floor: float, ceiling: float) -> float:
        """线性映射到 0-100。"""
        if value <= floor:
            return 0.0
        if value >= ceiling:
            return 100.0
        return (value - floor) / (ceiling - floor) * 100.0

    @staticmethod
    def _inverse_score(value: float, floor: float, ceiling: float) -> float:
        """反向线性映射到 0-100（值越小得分越高）。"""
        if value <= floor:
            return 100.0
        if value >= ceiling:
            return 0.0
        return (ceiling - value) / (ceiling - floor) * 100.0

    @staticmethod
    def _grade(score: float) -> str:
        """根据总分评级。"""
        if score >= 80:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 40:
            return "C"
        elif score >= 20:
            return "D"
        else:
            return "F"
