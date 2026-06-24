"""实验优化系统 - 参数扫描、优化、实验记录。

功能：
  - 网格搜索（Grid Search）
  - 随机搜索（Random Search）
  - 市场状态检测（Regime Detection）
  - 策略评分系统（Scoring）
"""

from .engine import ExperimentEngine
from .regime import MarketRegimeDetector
from .scoring import StrategyScorer

__all__ = ["ExperimentEngine", "MarketRegimeDetector", "StrategyScorer"]
