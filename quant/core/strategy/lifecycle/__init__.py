"""策略生命周期管理 - 快照、审核、退役。

功能：
  - 策略快照系统（不可变记录）
  - 策略审核引擎（自动评分 + 准入门槛）
  - 策略状态机（draft → research → candidate → paper → production → retired）
  - 自动退役规则
"""

from .snapshot import StrategySnapshot, StrategySnapshotStore
from .review import StrategyReview, StrategyReviewEngine
from .lifecycle import StrategyLifecycleManager, StrategyStatus

__all__ = [
    "StrategySnapshot",
    "StrategySnapshotStore",
    "StrategyReview",
    "StrategyReviewEngine",
    "StrategyLifecycleManager",
    "StrategyStatus",
]
