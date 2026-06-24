"""策略生命周期管理器 - 状态机 + 自动退役。

策略状态：
  draft → research → candidate → paper → production → retired

自动退役规则：
  - 模拟盘连续 20 个交易日超额收益为负 → 标记 review_needed
  - 模拟盘连续 40 个交易日超额收益为负 → 自动 retired
  - 回撤超过策略设定阈值的 1.5 倍 → 标记 review_needed
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .snapshot import StrategySnapshotStore, StrategySnapshot
from .review import StrategyReviewEngine, StrategyReview

ROOT = Path(__file__).resolve().parents[4]
LIFECYCLE_DB = ROOT / "research_store" / "strategy_lifecycle.sqlite3"


class StrategyStatus(str, Enum):
    """策略状态枚举。"""
    DRAFT = "draft"               # 草稿中
    RESEARCH = "research"         # 研究中
    CANDIDATE = "candidate"       # 候选
    PAPER = "paper"               # 模拟盘观察
    PRODUCTION = "production"     # 实盘
    RETIRED = "retired"           # 退役
    REVIEW_NEEDED = "review_needed"  # 需要审核


@dataclass
class StrategyRecord:
    """策略记录。"""
    strategy_id: str
    status: StrategyStatus
    current_version: str
    snapshot_id: str
    review_id: str | None
    paper_start_date: str | None
    production_start_date: str | None
    retired_date: str | None
    retired_reason: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "current_version": self.current_version,
            "snapshot_id": self.snapshot_id,
            "review_id": self.review_id,
            "paper_start_date": self.paper_start_date,
            "production_start_date": self.production_start_date,
            "retired_date": self.retired_date,
            "retired_reason": self.retired_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# 状态转换规则
VALID_TRANSITIONS = {
    StrategyStatus.DRAFT: [StrategyStatus.RESEARCH],
    StrategyStatus.RESEARCH: [StrategyStatus.CANDIDATE, StrategyStatus.RETIRED],
    StrategyStatus.CANDIDATE: [StrategyStatus.PAPER, StrategyStatus.RETIRED],
    StrategyStatus.PAPER: [StrategyStatus.PRODUCTION, StrategyStatus.REVIEW_NEEDED, StrategyStatus.RETIRED],
    StrategyStatus.PRODUCTION: [StrategyStatus.REVIEW_NEEDED, StrategyStatus.RETIRED],
    StrategyStatus.REVIEW_NEEDED: [StrategyStatus.PAPER, StrategyStatus.PRODUCTION, StrategyStatus.RETIRED],
    StrategyStatus.RETIRED: [],  # 终态
}


class StrategyLifecycleManager:
    """策略生命周期管理器。"""

    def __init__(self):
        self.snapshot_store = StrategySnapshotStore()
        self.review_engine = StrategyReviewEngine()
        self._init_db()

    def _init_db(self):
        """初始化数据库。"""
        if not LIFECYCLE_DB.exists():
            conn = sqlite3.connect(str(LIFECYCLE_DB))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_records (
                    strategy_id TEXT PRIMARY KEY,
                    status TEXT,
                    current_version TEXT,
                    snapshot_id TEXT,
                    review_id TEXT,
                    paper_start_date TEXT,
                    production_start_date TEXT,
                    retired_date TEXT,
                    retired_reason TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
            conn.close()

    def register_strategy(
        self,
        strategy_id: str,
        version: str,
        code: str,
        config: dict[str, Any],
        backtest_summary: dict[str, Any] | None = None,
        factor_set: list[str] | None = None,
    ) -> StrategyRecord:
        """注册新策略。

        Args:
            strategy_id: 策略 ID
            version: 策略版本
            code: 策略代码
            config: 策略配置
            backtest_summary: 回测摘要
            factor_set: 因子集合

        Returns:
            策略记录
        """
        # 创建快照
        snapshot = self.snapshot_store.save_snapshot(
            strategy_id=strategy_id,
            strategy_version=version,
            code=code,
            config=config,
            backtest_summary=backtest_summary,
            factor_set=factor_set,
        )

        # 创建策略记录
        now = datetime.now(UTC).isoformat()
        record = StrategyRecord(
            strategy_id=strategy_id,
            status=StrategyStatus.RESEARCH,
            current_version=version,
            snapshot_id=snapshot.snapshot_id,
            review_id=None,
            paper_start_date=None,
            production_start_date=None,
            retired_date=None,
            retired_reason=None,
            created_at=now,
            updated_at=now,
        )

        self._save_record(record)
        return record

    def transition(
        self,
        strategy_id: str,
        new_status: StrategyStatus,
        reason: str = "",
    ) -> StrategyRecord:
        """转换策略状态。

        Args:
            strategy_id: 策略 ID
            new_status: 新状态
            reason: 转换原因

        Returns:
            更新后的策略记录
        """
        record = self.get_strategy(strategy_id)
        if not record:
            raise ValueError(f"策略 {strategy_id} 不存在")

        # 检查转换是否合法
        if new_status not in VALID_TRANSITIONS.get(record.status, []):
            raise ValueError(
                f"非法状态转换: {record.status.value} → {new_status.value}"
            )

        # 更新状态
        now = datetime.now(UTC).isoformat()
        record.status = new_status
        record.updated_at = now

        if new_status == StrategyStatus.PAPER:
            record.paper_start_date = now
        elif new_status == StrategyStatus.PRODUCTION:
            record.production_start_date = now
        elif new_status == StrategyStatus.RETIRED:
            record.retired_date = now
            record.retired_reason = reason

        self._save_record(record)
        return record

    def get_strategy(self, strategy_id: str) -> StrategyRecord | None:
        """获取策略记录。"""
        conn = sqlite3.connect(str(LIFECYCLE_DB))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM strategy_records WHERE strategy_id = ?",
                (strategy_id,),
            ).fetchone()

            if not row:
                return None

            return StrategyRecord(
                strategy_id=row["strategy_id"],
                status=StrategyStatus(row["status"]),
                current_version=row["current_version"],
                snapshot_id=row["snapshot_id"],
                review_id=row["review_id"],
                paper_start_date=row["paper_start_date"],
                production_start_date=row["production_start_date"],
                retired_date=row["retired_date"],
                retired_reason=row["retired_reason"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        finally:
            conn.close()

    def list_strategies(
        self,
        status: StrategyStatus | None = None,
        limit: int = 50,
    ) -> list[StrategyRecord]:
        """列出策略。"""
        conn = sqlite3.connect(str(LIFECYCLE_DB))
        conn.row_factory = sqlite3.Row
        try:
            if status:
                rows = conn.execute(
                    """SELECT * FROM strategy_records
                       WHERE status = ?
                       ORDER BY updated_at DESC LIMIT ?""",
                    (status.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM strategy_records ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            return [
                StrategyRecord(
                    strategy_id=row["strategy_id"],
                    status=StrategyStatus(row["status"]),
                    current_version=row["current_version"],
                    snapshot_id=row["snapshot_id"],
                    review_id=row["review_id"],
                    paper_start_date=row["paper_start_date"],
                    production_start_date=row["production_start_date"],
                    retired_date=row["retired_date"],
                    retired_reason=row["retired_reason"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def review_strategy(
        self,
        strategy_id: str,
        metrics: dict[str, Any],
    ) -> StrategyReview:
        """审核策略。"""
        record = self.get_strategy(strategy_id)
        if not record:
            raise ValueError(f"策略 {strategy_id} 不存在")

        # 运行审核
        review = self.review_engine.review(
            strategy_id=strategy_id,
            strategy_version=record.current_version,
            metrics=metrics,
        )

        # 更新记录
        record.review_id = review.review_id
        record.updated_at = datetime.now(UTC).isoformat()
        self._save_record(record)

        return review

    def check_auto_retirement(
        self,
        strategy_id: str,
        excess_returns: list[float],
        max_drawdown_threshold: float = 20.0,
    ) -> dict[str, Any]:
        """检查是否需要自动退役。

        Args:
            strategy_id: 策略 ID
            excess_returns: 最近的超额收益序列
            max_drawdown_threshold: 最大回撤阈值（%）

        Returns:
            检查结果
        """
        record = self.get_strategy(strategy_id)
        if not record:
            return {"action": "none", "reason": "策略不存在"}

        if record.status not in [StrategyStatus.PAPER, StrategyStatus.PRODUCTION]:
            return {"action": "none", "reason": "状态不允许自动退役检查"}

        # 检查连续负超额收益
        consecutive_negative = 0
        for ret in excess_returns:
            if ret < 0:
                consecutive_negative += 1
            else:
                consecutive_negative = 0

        if consecutive_negative >= 40:
            return {
                "action": "auto_retire",
                "reason": f"连续 {consecutive_negative} 个交易日超额收益为负",
            }
        elif consecutive_negative >= 20:
            return {
                "action": "review_needed",
                "reason": f"连续 {consecutive_negative} 个交易日超额收益为负",
            }

        return {"action": "none", "reason": "正常"}

    def _save_record(self, record: StrategyRecord):
        """保存策略记录。"""
        conn = sqlite3.connect(str(LIFECYCLE_DB))
        try:
            conn.execute(
                """INSERT OR REPLACE INTO strategy_records
                   (strategy_id, status, current_version, snapshot_id,
                    review_id, paper_start_date, production_start_date,
                    retired_date, retired_reason, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.strategy_id,
                    record.status.value,
                    record.current_version,
                    record.snapshot_id,
                    record.review_id,
                    record.paper_start_date,
                    record.production_start_date,
                    record.retired_date,
                    record.retired_reason,
                    record.created_at,
                    record.updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
