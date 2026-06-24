"""策略审核引擎 - 自动评分和准入检查。

评分维度：
  - 夏普比率（权重高）
  - 最大回撤（权重高）
  - 年化收益（权重中）
  - 超额收益（权重高）
  - 稳定性（权重中）
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

DB_PATH = Path("research_store/strategy_reviews.sqlite3")


class ReviewDecision(str, Enum):
    """审核决定。"""
    APPROVE = "approve"       # 批准
    REJECT = "reject"         # 拒绝
    REVISE = "revise"         # 需要修改
    PENDING = "pending"       # 待审核


@dataclass
class CriterionResult:
    """单项检查结果。"""
    name: str
    passed: bool
    value: float
    threshold: float
    weight: float
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "value": self.value,
            "threshold": self.threshold,
            "weight": self.weight,
            "message": self.message,
        }


@dataclass
class StrategyReview:
    """策略审核记录。"""
    review_id: str
    strategy_id: str
    strategy_version: str
    reviewer: str                    # "auto" 或 "manual"
    decision: ReviewDecision
    score: float                     # 总分 (0-100)
    criteria_results: list[CriterionResult]
    notes: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "reviewer": self.reviewer,
            "decision": self.decision.value,
            "score": self.score,
            "criteria_results": [c.to_dict() for c in self.criteria_results],
            "notes": self.notes,
            "created_at": self.created_at,
        }


# 评分标准
CRITERIA_CONFIG = [
    {
        "name": "sharpe_ratio",
        "display_name": "夏普比率",
        "threshold": 0.8,
        "weight": 0.25,
        "direction": "higher_better",
    },
    {
        "name": "max_drawdown",
        "display_name": "最大回撤",
        "threshold": -0.20,  # -20%
        "weight": 0.25,
        "direction": "lower_better",
    },
    {
        "name": "annual_return",
        "display_name": "年化收益",
        "threshold": 0.10,  # 10%
        "weight": 0.15,
        "direction": "higher_better",
    },
    {
        "name": "excess_return",
        "display_name": "超额收益",
        "threshold": 0.0,  # 0%
        "weight": 0.25,
        "direction": "higher_better",
    },
    {
        "name": "stability",
        "display_name": "收益稳定性",
        "threshold": 0.5,  # 正收益天数比例 > 50%
        "weight": 0.10,
        "direction": "higher_better",
    },
]


class StrategyReviewEngine:
    """策略审核引擎。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self):
        """初始化数据库表。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_reviews (
                    review_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    reviewer TEXT DEFAULT 'auto',
                    decision TEXT NOT NULL,
                    score REAL NOT NULL,
                    criteria_results_json TEXT DEFAULT '[]',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_strategy_id
                ON strategy_reviews(strategy_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def review(
        self,
        strategy_id: str,
        strategy_version: str,
        metrics: dict[str, float],
        reviewer: str = "auto",
    ) -> StrategyReview:
        """执行策略审核。

        Args:
            strategy_id: 策略ID
            strategy_version: 策略版本
            metrics: 回测指标 (sharpe, max_drawdown, annual_return, excess_return, stability)
            reviewer: 审核者 ("auto" 或 "manual")

        Returns:
            StrategyReview 审核结果
        """
        criteria_results = []
        total_score = 0.0

        for config in CRITERIA_CONFIG:
            name = config["name"]
            value = metrics.get(name, 0.0)
            threshold = config["threshold"]
            weight = config["weight"]

            # 判断是否通过
            if config["direction"] == "higher_better":
                passed = value >= threshold
                # 计算得分：超过阈值越多分越高
                if threshold > 0:
                    score = min(100, (value / threshold) * 100)
                else:
                    score = 100 if value > 0 else 0
            else:  # lower_better (e.g., max_drawdown)
                passed = value >= threshold  # threshold is negative
                # 计算得分：回撤越小分越高
                if threshold < 0:
                    score = min(100, (1 - value / threshold) * 100)
                else:
                    score = 100 if value >= 0 else 0

            criteria_results.append(CriterionResult(
                name=name,
                passed=passed,
                value=value,
                threshold=threshold,
                weight=weight,
                message=f"{config['display_name']}: {value:.4f} (阈值: {threshold:.4f})",
            ))

            total_score += score * weight

        # 决定审核结果
        if total_score >= 80:
            decision = ReviewDecision.APPROVE
        elif total_score >= 60:
            decision = ReviewDecision.REVISE
        else:
            decision = ReviewDecision.REJECT

        now = datetime.now(UTC).isoformat()
        review_id = f"review_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"

        review = StrategyReview(
            review_id=review_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            reviewer=reviewer,
            decision=decision,
            score=total_score,
            criteria_results=criteria_results,
            notes=f"自动审核得分: {total_score:.1f}/100",
            created_at=now,
        )

        # 保存审核记录
        self._save_review(review)

        return review

    def _save_review(self, review: StrategyReview):
        """保存审核记录。"""
        import json

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT INTO strategy_reviews
                   (review_id, strategy_id, strategy_version, reviewer,
                    decision, score, criteria_results_json, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.strategy_id,
                    review.strategy_version,
                    review.reviewer,
                    review.decision.value,
                    review.score,
                    json.dumps([c.to_dict() for c in review.criteria_results]),
                    review.notes,
                    review.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest_review(self, strategy_id: str) -> StrategyReview | None:
        """获取最新审核记录。"""
        import json

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT * FROM strategy_reviews
                   WHERE strategy_id = ?
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (strategy_id,),
            ).fetchone()

            if not row:
                return None

            criteria_data = json.loads(row["criteria_results_json"])
            criteria_results = [
                CriterionResult(**c) for c in criteria_data
            ]

            return StrategyReview(
                review_id=row["review_id"],
                strategy_id=row["strategy_id"],
                strategy_version=row["strategy_version"],
                reviewer=row["reviewer"],
                decision=ReviewDecision(row["decision"]),
                score=row["score"],
                criteria_results=criteria_results,
                notes=row["notes"],
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def list_reviews(self, strategy_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """列出审核记录。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT * FROM strategy_reviews
                   WHERE strategy_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (strategy_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
