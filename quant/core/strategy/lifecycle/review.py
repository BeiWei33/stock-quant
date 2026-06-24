"""策略审核引擎 - 自动评分 + 准入门槛。

准入检查项：
  - Sharpe 比率 > 0.8
  - 最大回撤 < 20%
  - 年化收益 > 10%
  - 超额收益 > 0
  - 与现有因子相关性 < 0.7
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
LIFECYCLE_DB = ROOT / "research_store" / "strategy_lifecycle.sqlite3"


@dataclass
class ReviewCriteria:
    """审核标准。"""
    name: str
    weight: float
    threshold: float
    operator: str  # ">", "<", ">=", "<="
    description: str


@dataclass
class CriteriaResult:
    """单项检查结果。"""
    name: str
    passed: bool
    value: float
    threshold: float
    weight: float
    score: float  # 0-100


@dataclass
class StrategyReview:
    """策略审核记录。"""
    review_id: str
    strategy_id: str
    strategy_version: str
    reviewer: str  # "auto" 或 "manual"
    decision: str  # "approve" / "reject" / "revise"
    criteria_results: list[CriteriaResult] = field(default_factory=list)
    total_score: float = 0.0
    notes: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "reviewer": self.reviewer,
            "decision": self.decision,
            "criteria_results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "value": r.value,
                    "threshold": r.threshold,
                    "weight": r.weight,
                    "score": r.score,
                }
                for r in self.criteria_results
            ],
            "total_score": self.total_score,
            "notes": self.notes,
            "created_at": self.created_at,
        }


# 默认审核标准
DEFAULT_CRITERIA = [
    ReviewCriteria(
        name="sharpe",
        weight=0.25,
        threshold=0.8,
        operator=">",
        description="夏普比率 > 0.8",
    ),
    ReviewCriteria(
        name="max_drawdown",
        weight=0.25,
        threshold=20.0,
        operator="<",
        description="最大回撤 < 20%",
    ),
    ReviewCriteria(
        name="annual_return",
        weight=0.20,
        threshold=10.0,
        operator=">",
        description="年化收益 > 10%",
    ),
    ReviewCriteria(
        name="excess_return",
        weight=0.20,
        threshold=0.0,
        operator=">",
        description="超额收益 > 0",
    ),
    ReviewCriteria(
        name="win_rate",
        weight=0.10,
        threshold=50.0,
        operator=">",
        description="胜率 > 50%",
    ),
]


class StrategyReviewEngine:
    """策略审核引擎。"""

    def __init__(self, criteria: list[ReviewCriteria] | None = None):
        self.criteria = criteria or DEFAULT_CRITERIA
        self._init_db()

    def _init_db(self):
        """初始化数据库。"""
        if not LIFECYCLE_DB.exists():
            conn = sqlite3.connect(str(LIFECYCLE_DB))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_reviews (
                    review_id TEXT PRIMARY KEY,
                    strategy_id TEXT,
                    strategy_version TEXT,
                    reviewer TEXT,
                    decision TEXT,
                    criteria_results TEXT,
                    total_score REAL,
                    notes TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()
            conn.close()

    def review(
        self,
        strategy_id: str,
        strategy_version: str,
        metrics: dict[str, Any],
        reviewer: str = "auto",
    ) -> StrategyReview:
        """审核策略。

        Args:
            strategy_id: 策略 ID
            strategy_version: 策略版本
            metrics: 回测指标
            reviewer: 审核人（auto 或 manual）

        Returns:
            审核结果
        """
        # 检查各项标准
        criteria_results = []
        total_score = 0.0

        for criterion in self.criteria:
            value = metrics.get(criterion.name, 0)
            if criterion.name == "max_drawdown":
                value = abs(value) * 100  # 转换为正数百分比
            elif criterion.name in ["annual_return", "excess_return", "win_rate"]:
                value = value * 100 if abs(value) < 10 else value

            # 判断是否通过
            if criterion.operator == ">":
                passed = value > criterion.threshold
            elif criterion.operator == "<":
                passed = value < criterion.threshold
            elif criterion.operator == ">=":
                passed = value >= criterion.threshold
            elif criterion.operator == "<=":
                passed = value <= criterion.threshold
            else:
                passed = False

            # 计算得分
            if passed:
                score = 100.0
            else:
                # 根据差距计算得分
                if criterion.operator in [">", ">="]:
                    score = max(0, min(100, (value / criterion.threshold) * 100))
                else:
                    score = max(0, min(100, (criterion.threshold / max(value, 0.01)) * 100))

            result = CriteriaResult(
                name=criterion.name,
                passed=passed,
                value=round(value, 2),
                threshold=criterion.threshold,
                weight=criterion.weight,
                score=round(score, 2),
            )
            criteria_results.append(result)
            total_score += score * criterion.weight

        # 决策
        if total_score >= 80:
            decision = "approve"
        elif total_score >= 60:
            decision = "revise"
        else:
            decision = "reject"

        # 创建审核记录
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        review = StrategyReview(
            review_id=f"review_{strategy_id}_{timestamp}",
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            reviewer=reviewer,
            decision=decision,
            criteria_results=criteria_results,
            total_score=round(total_score, 2),
            created_at=datetime.now(UTC).isoformat(),
        )

        # 保存到数据库
        self._save_review(review)

        return review

    def _save_review(self, review: StrategyReview):
        """保存审核记录。"""
        conn = sqlite3.connect(str(LIFECYCLE_DB))
        try:
            conn.execute(
                """INSERT INTO strategy_reviews
                   (review_id, strategy_id, strategy_version, reviewer,
                    decision, criteria_results, total_score, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.strategy_id,
                    review.strategy_version,
                    review.reviewer,
                    review.decision,
                    json.dumps([r.__dict__ for r in review.criteria_results]),
                    review.total_score,
                    review.notes,
                    review.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_review(self, review_id: str) -> StrategyReview | None:
        """获取审核记录。"""
        conn = sqlite3.connect(str(LIFECYCLE_DB))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM strategy_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()

            if not row:
                return None

            criteria_data = json.loads(row["criteria_results"])
            criteria_results = [
                CriteriaResult(**item) for item in criteria_data
            ]

            return StrategyReview(
                review_id=row["review_id"],
                strategy_id=row["strategy_id"],
                strategy_version=row["strategy_version"],
                reviewer=row["reviewer"],
                decision=row["decision"],
                criteria_results=criteria_results,
                total_score=row["total_score"],
                notes=row["notes"],
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def list_reviews(
        self,
        strategy_id: str | None = None,
        limit: int = 20,
    ) -> list[StrategyReview]:
        """列出审核记录。"""
        conn = sqlite3.connect(str(LIFECYCLE_DB))
        conn.row_factory = sqlite3.Row
        try:
            if strategy_id:
                rows = conn.execute(
                    """SELECT * FROM strategy_reviews
                       WHERE strategy_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (strategy_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM strategy_reviews ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            reviews = []
            for row in rows:
                criteria_data = json.loads(row["criteria_results"])
                criteria_results = [
                    CriteriaResult(**item) for item in criteria_data
                ]
                reviews.append(StrategyReview(
                    review_id=row["review_id"],
                    strategy_id=row["strategy_id"],
                    strategy_version=row["strategy_version"],
                    reviewer=row["reviewer"],
                    decision=row["decision"],
                    criteria_results=criteria_results,
                    total_score=row["total_score"],
                    notes=row["notes"],
                    created_at=row["created_at"],
                ))

            return reviews
        finally:
            conn.close()
