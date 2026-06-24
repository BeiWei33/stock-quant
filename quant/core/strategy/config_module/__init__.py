"""策略配置标准化 - 定义策略配置结构。

功能：
  - 策略配置 JSON Schema 定义
  - 策略快照管理
  - 策略生命周期状态机
  - 策略审核引擎
"""

from .config import (
    StrategyConfig,
    RiskConfig,
    PositionConfig,
    ExecutionConfig,
    IndicatorConfig,
)
from .snapshot import StrategySnapshot, StrategySnapshotStore
from .lifecycle import StrategyStatus, StrategyLifecycleManager
from .review import StrategyReview, StrategyReviewEngine

__all__ = [
    "StrategyConfig",
    "RiskConfig",
    "PositionConfig",
    "ExecutionConfig",
    "IndicatorConfig",
    "StrategySnapshot",
    "StrategySnapshotStore",
    "StrategyStatus",
    "StrategyLifecycleManager",
    "StrategyReview",
    "StrategyReviewEngine",
]
