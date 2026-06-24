"""策略配置结构定义。

定义标准化的策略配置格式，支持：
  - 基本信息（名称、描述、版本）
  - 风险管理（止损、止盈、追踪止损）
  - 仓位管理（初始仓位、加仓、减仓）
  - 执行配置（信号时机、滑点、佣金）
  - 指标配置（因子、参数）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json


@dataclass(frozen=True)
class RiskConfig:
    """风险管理配置。"""
    stop_loss_pct: float = 0.0          # 止损百分比 (0.05 = 5%)
    take_profit_pct: float = 0.0        # 止盈百分比
    trailing_stop_pct: float = 0.0      # 追踪止损百分比
    trailing_activation_pct: float = 0.0  # 追踪止损激活点
    max_drawdown_pct: float = 0.0       # 最大回撤限制

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "trailing_activation_pct": self.trailing_activation_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RiskConfig:
        if not data:
            return cls()
        return cls(
            stop_loss_pct=float(data.get("stop_loss_pct", 0)),
            take_profit_pct=float(data.get("take_profit_pct", 0)),
            trailing_stop_pct=float(data.get("trailing_stop_pct", 0)),
            trailing_activation_pct=float(data.get("trailing_activation_pct", 0)),
            max_drawdown_pct=float(data.get("max_drawdown_pct", 0)),
        )


@dataclass(frozen=True)
class PositionConfig:
    """仓位管理配置。"""
    initial_size_pct: float = 100.0     # 初始仓位百分比 (100 = 全仓)
    max_holdings: int = 20              # 最大持仓数量
    max_single_weight: float = 0.10     # 单只股票最大权重
    max_industry_weight: float = 0.30   # 单行业最大权重
    cash_reserve: float = 0.10          # 现金保留比例

    # 加仓配置
    trend_add_enabled: bool = False     # 趋势加仓
    trend_add_step_pct: float = 0.0     # 加仓步长
    trend_add_size_pct: float = 0.0     # 加仓比例
    trend_add_max_times: int = 0        # 最大加仓次数

    # 减仓配置
    trend_reduce_enabled: bool = False  # 趋势减仓
    trend_reduce_step_pct: float = 0.0  # 减仓步长
    trend_reduce_size_pct: float = 0.0  # 减仓比例
    trend_reduce_max_times: int = 0     # 最大减仓次数

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_size_pct": self.initial_size_pct,
            "max_holdings": self.max_holdings,
            "max_single_weight": self.max_single_weight,
            "max_industry_weight": self.max_industry_weight,
            "cash_reserve": self.cash_reserve,
            "trend_add_enabled": self.trend_add_enabled,
            "trend_add_step_pct": self.trend_add_step_pct,
            "trend_add_size_pct": self.trend_add_size_pct,
            "trend_add_max_times": self.trend_add_max_times,
            "trend_reduce_enabled": self.trend_reduce_enabled,
            "trend_reduce_step_pct": self.trend_reduce_step_pct,
            "trend_reduce_size_pct": self.trend_reduce_size_pct,
            "trend_reduce_max_times": self.trend_reduce_max_times,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PositionConfig:
        if not data:
            return cls()
        return cls(
            initial_size_pct=float(data.get("initial_size_pct", 100)),
            max_holdings=int(data.get("max_holdings", 20)),
            max_single_weight=float(data.get("max_single_weight", 0.10)),
            max_industry_weight=float(data.get("max_industry_weight", 0.30)),
            cash_reserve=float(data.get("cash_reserve", 0.10)),
            trend_add_enabled=bool(data.get("trend_add_enabled", False)),
            trend_add_step_pct=float(data.get("trend_add_step_pct", 0)),
            trend_add_size_pct=float(data.get("trend_add_size_pct", 0)),
            trend_add_max_times=int(data.get("trend_add_max_times", 0)),
            trend_reduce_enabled=bool(data.get("trend_reduce_enabled", False)),
            trend_reduce_step_pct=float(data.get("trend_reduce_step_pct", 0)),
            trend_reduce_size_pct=float(data.get("trend_reduce_size_pct", 0)),
            trend_reduce_max_times=int(data.get("trend_reduce_max_times", 0)),
        )


@dataclass(frozen=True)
class ExecutionConfig:
    """执行配置。"""
    signal_timing: str = "next_bar_open"  # 信号时机: next_bar_open / same_bar_close
    commission_rate: float = 0.0003       # 佣金费率
    slippage_bps: float = 0.0             # 滑点 (基点)
    min_commission: float = 5.0           # 最低佣金
    stamp_tax_rate: float = 0.0005        # 印花税率

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_timing": self.signal_timing,
            "commission_rate": self.commission_rate,
            "slippage_bps": self.slippage_bps,
            "min_commission": self.min_commission,
            "stamp_tax_rate": self.stamp_tax_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ExecutionConfig:
        if not data:
            return cls()
        return cls(
            signal_timing=str(data.get("signal_timing", "next_bar_open")),
            commission_rate=float(data.get("commission_rate", 0.0003)),
            slippage_bps=float(data.get("slippage_bps", 0)),
            min_commission=float(data.get("min_commission", 5)),
            stamp_tax_rate=float(data.get("stamp_tax_rate", 0.0005)),
        )


@dataclass(frozen=True)
class IndicatorConfig:
    """指标配置。"""
    factor_name: str = ""                 # 因子名称
    factor_params: dict[str, Any] = field(default_factory=dict)  # 因子参数

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "factor_params": self.factor_params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> IndicatorConfig:
        if not data:
            return cls()
        return cls(
            factor_name=str(data.get("factor_name", "")),
            factor_params=dict(data.get("factor_params", {})),
        )


@dataclass(frozen=True)
class StrategyConfig:
    """完整策略配置。"""
    strategy_id: str = ""                 # 策略ID
    strategy_name: str = ""               # 策略名称
    strategy_version: str = "v1"          # 策略版本
    strategy_type: str = "momentum_rank"  # 策略类型
    description: str = ""                 # 策略描述

    # 子配置
    risk: RiskConfig = field(default_factory=RiskConfig)
    position: PositionConfig = field(default_factory=PositionConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    indicator: IndicatorConfig = field(default_factory=IndicatorConfig)

    # 元数据
    created_at: str = ""
    updated_at: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "strategy_type": self.strategy_type,
            "description": self.description,
            "risk": self.risk.to_dict(),
            "position": self.position.to_dict(),
            "execution": self.execution.to_dict(),
            "indicator": self.indicator.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "author": self.author,
            "tags": self.tags,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyConfig:
        return cls(
            strategy_id=str(data.get("strategy_id", "")),
            strategy_name=str(data.get("strategy_name", "")),
            strategy_version=str(data.get("strategy_version", "v1")),
            strategy_type=str(data.get("strategy_type", "momentum_rank")),
            description=str(data.get("description", "")),
            risk=RiskConfig.from_dict(data.get("risk")),
            position=PositionConfig.from_dict(data.get("position")),
            execution=ExecutionConfig.from_dict(data.get("execution")),
            indicator=IndicatorConfig.from_dict(data.get("indicator")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            author=str(data.get("author", "")),
            tags=list(data.get("tags", [])),
        )

    @classmethod
    def from_json(cls, json_str: str) -> StrategyConfig:
        return cls.from_dict(json.loads(json_str))


# 预置策略配置模板
PRESET_CONFIGS = {
    "momentum_rank": StrategyConfig(
        strategy_type="momentum_rank",
        strategy_name="动量排名策略",
        description="基于动量因子选股，持有排名靠前的股票",
        position=PositionConfig(max_holdings=20),
        indicator=IndicatorConfig(factor_name="momentum_60d"),
    ),
    "quality_rank": StrategyConfig(
        strategy_type="quality_rank",
        strategy_name="质量排名策略",
        description="基于质量因子选股，持有质量评分最高的股票",
        position=PositionConfig(max_holdings=20),
        indicator=IndicatorConfig(factor_name="quality_score"),
    ),
    "momentum_rank_trend": StrategyConfig(
        strategy_type="momentum_rank_trend",
        strategy_name="动量+趋势策略",
        description="动量因子选股，叠加趋势过滤",
        position=PositionConfig(max_holdings=20),
        indicator=IndicatorConfig(factor_name="momentum_60d"),
        risk=RiskConfig(stop_loss_pct=0.05),
    ),
    "quality_rank_trend": StrategyConfig(
        strategy_type="quality_rank_trend",
        strategy_name="质量+趋势策略",
        description="质量因子选股，叠加趋势过滤",
        position=PositionConfig(max_holdings=20),
        indicator=IndicatorConfig(factor_name="quality_score"),
        risk=RiskConfig(stop_loss_pct=0.05),
    ),
}
