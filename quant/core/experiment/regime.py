"""市场状态检测 - 判断当前市场处于何种状态。

市场状态：
  - bull_trend: 牛市趋势
  - bear_trend: 熊市趋势
  - range_compression: 震荡盘整
  - high_volatility: 高波动
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class RegimeResult:
    """市场状态检测结果。"""
    regime: str
    confidence: float
    features: dict[str, float]
    description: str


class MarketRegimeDetector:
    """市场状态检测器。"""

    REGIME_PROFILES = {
        "bull_trend": {
            "label": "牛市趋势",
            "description": "市场处于上升趋势，适合趋势跟踪策略",
            "strategy_families": ["trend_following", "breakout", "momentum"],
        },
        "bear_trend": {
            "label": "熊市趋势",
            "description": "市场处于下降趋势，适合防守或做空策略",
            "strategy_families": ["defensive", "short", "low_volatility"],
        },
        "range_compression": {
            "label": "震荡盘整",
            "description": "市场在区间内震荡，适合均值回归策略",
            "strategy_families": ["mean_reversion", "range_trading"],
        },
        "high_volatility": {
            "label": "高波动",
            "description": "市场波动剧烈，需要降低仓位或等待",
            "strategy_families": ["volatility_breakout", "reduced_position"],
        },
    }

    def detect(self, bars: pd.DataFrame, lookback_days: int = 60) -> RegimeResult:
        """检测市场状态。

        Args:
            bars: 日线数据
            lookback_days: 回看天数

        Returns:
            市场状态检测结果
        """
        # 计算特征
        features = self._extract_features(bars, lookback_days)

        # 分类
        regime, confidence = self._classify(features)

        # 获取描述
        profile = self.REGIME_PROFILES.get(regime, {})

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 2),
            features=features,
            description=profile.get("description", ""),
        )

    def detect_from_equity_curve(self, equity_curve: list[dict[str, Any]]) -> RegimeResult:
        """从净值曲线检测市场状态。

        Args:
            equity_curve: 净值曲线数据

        Returns:
            市场状态检测结果
        """
        if not equity_curve or len(equity_curve) < 30:
            return RegimeResult(
                regime="unknown",
                confidence=0.0,
                features={},
                description="数据不足，无法判断市场状态",
            )

        # 提取净值序列
        values = [p.get("equity", p.get("total_asset", 0)) for p in equity_curve]
        series = pd.Series(values)

        # 计算特征
        returns = series.pct_change().dropna()
        if len(returns) < 20:
            return RegimeResult(
                regime="unknown",
                confidence=0.0,
                features={},
                description="数据不足",
            )

        features = {
            "total_return": (series.iloc[-1] / series.iloc[0] - 1) * 100,
            "volatility": returns.std() * (252 ** 0.5) * 100,  # 年化波动率
            "max_drawdown": self._max_drawdown(series) * 100,
            "trend_strength": self._trend_strength(series),
        }

        regime, confidence = self._classify(features)

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 2),
            features=features,
            description=self.REGIME_PROFILES.get(regime, {}).get("description", ""),
        )

    def _extract_features(self, bars: pd.DataFrame, lookback_days: int) -> dict[str, float]:
        """提取市场特征。"""
        # 计算全市场等权收益
        close = bars.pivot(index="trade_date", columns="ts_code", values="close")
        market_return = close.pct_change().mean(axis=1)

        # 取最近 N 天
        recent = market_return.tail(lookback_days)

        if len(recent) < 20:
            return {}

        # 计算特征
        total_return = (1 + recent).prod() - 1
        volatility = recent.std() * (252 ** 0.5)
        max_dd = self._max_drawdown_from_returns(recent)
        trend_strength = self._trend_strength_from_returns(recent)

        return {
            "total_return": round(total_return * 100, 2),
            "volatility": round(volatility * 100, 2),
            "max_drawdown": round(max_dd * 100, 2),
            "trend_strength": round(trend_strength, 2),
        }

    def _classify(self, features: dict[str, float]) -> tuple[str, float]:
        """根据特征分类市场状态。"""
        if not features:
            return "unknown", 0.0

        total_return = features.get("total_return", 0)
        volatility = features.get("volatility", 20)
        max_dd = features.get("max_drawdown", 10)
        trend_strength = features.get("trend_strength", 0)

        # 规则分类
        scores = {
            "bull_trend": 0.0,
            "bear_trend": 0.0,
            "range_compression": 0.0,
            "high_volatility": 0.0,
        }

        # 牛市条件：正收益、趋势强、回撤小
        if total_return > 10:
            scores["bull_trend"] += 0.4
        elif total_return > 0:
            scores["bull_trend"] += 0.2

        if trend_strength > 0.6:
            scores["bull_trend"] += 0.3

        if max_dd < 10:
            scores["bull_trend"] += 0.2

        # 熊市条件：负收益、趋势弱
        if total_return < -10:
            scores["bear_trend"] += 0.4
        elif total_return < 0:
            scores["bear_trend"] += 0.2

        if trend_strength < 0.4:
            scores["bear_trend"] += 0.2

        if max_dd > 15:
            scores["bear_trend"] += 0.2

        # 震荡条件：收益接近0、波动中等
        if abs(total_return) < 5:
            scores["range_compression"] += 0.4

        if 10 < volatility < 25:
            scores["range_compression"] += 0.3

        if trend_strength < 0.5:
            scores["range_compression"] += 0.2

        # 高波动条件：波动率高
        if volatility > 30:
            scores["high_volatility"] += 0.5
        elif volatility > 25:
            scores["high_volatility"] += 0.3

        if max_dd > 20:
            scores["high_volatility"] += 0.3

        # 选择最高分的状态
        best_regime = max(scores, key=scores.get)
        confidence = scores[best_regime]

        return best_regime, confidence

    @staticmethod
    def _max_drawdown(series: pd.Series) -> float:
        """计算最大回撤。"""
        peak = series.expanding().max()
        drawdown = (series - peak) / peak
        return abs(drawdown.min())

    @staticmethod
    def _max_drawdown_from_returns(returns: pd.Series) -> float:
        """从收益率序列计算最大回撤。"""
        cumulative = (1 + returns).cumprod()
        peak = cumulative.expanding().max()
        drawdown = (cumulative - peak) / peak
        return abs(drawdown.min())

    @staticmethod
    def _trend_strength(series: pd.Series) -> float:
        """计算趋势强度（0-1）。"""
        if len(series) < 10:
            return 0.5

        # 使用线性回归的 R² 作为趋势强度
        x = pd.Series(range(len(series)))
        correlation = x.corr(series)

        # 将相关系数转换为 0-1 范围
        return abs(correlation)

    @staticmethod
    def _trend_strength_from_returns(returns: pd.Series) -> float:
        """从收益率序列计算趋势强度。"""
        cumulative = (1 + returns).cumprod()
        x = pd.Series(range(len(cumulative)))
        correlation = x.corr(cumulative)
        return abs(correlation)
