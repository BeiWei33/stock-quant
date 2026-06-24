"""策略生命周期状态机。

状态流转：
  draft → research → candidate → paper → production
                                            ↓
              deprecated ←──────────────── retired
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

DB_PATH = Path("research_store/strategy_lifecycle.sqlite3")


class StrategyStatus(str, Enum):
    """策略状态枚举。"""
    DRAFT = "draft"               # 草稿中
    RESEARCH = "research"         # 研究中
    CANDIDATE = "candidate"       # 候选
    PAPER = "paper"               # 模拟盘观察
    PRODUCTION = "production"     # 实盘
    DEPRECATED = "deprecated"     # 已淘汰
    RETIRED = "retired"           # 退役

    @classmethod
    def from_str(cls, value: str) -> StrategyStatus:
        """从字符串转换。"""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.DRAFT


# 状态流转规则
VALID_TRANSITIONS = {
    StrategyStatus.DRAFT: [StrategyStatus.RESEARCH],
    StrategyStatus.RESEARCH: [StrategyStatus.CANDIDATE, StrategyStatus.DRAFT],
    StrategyStatus.CANDIDATE: [StrategyStatus.PAPER, StrategyStatus.RESEARCH, StrategyStatus.DEPRECATED],
    StrategyStatus.PAPER: [StrategyStatus.PRODUCTION, StrategyStatus.CANDIDATE, StrategyStatus.DEPRECATED],
    StrategyStatus.PRODUCTION: [StrategyStatus.RETIRED, StrategyStatus.DEPRECATED],
    StrategyStatus.DEPRECATED: [StrategyStatus.RETIRED],
    StrategyStatus.RETIRED: [],  # 终态
}


@dataclass
class StrategyLifecycle:
    """策略生命周期记录。"""
    strategy_id: str
    status: StrategyStatus
    status_changed_at: str
    status_changed_by: str
    reason: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "status_changed_at": self.status_changed_at,
            "status_changed_by": self.status_changed_by,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class StrategyLifecycleManager:
    """策略生命周期管理器。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self):
        """初始化数据库表。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_lifecycle (
                    strategy_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    status_changed_at TEXT NOT NULL,
                    status_changed_by TEXT DEFAULT 'system',
                    reason TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_lifecycle_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT DEFAULT 'system',
                    reason TEXT DEFAULT ''
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get_status(self, strategy_id: str) -> StrategyStatus:
        """获取策略当前状态。"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT status FROM strategy_lifecycle WHERE strategy_id = ?",
                (strategy_id,),
            ).fetchone()
            if not row:
                return StrategyStatus.DRAFT
            return StrategyStatus.from_str(row[0])
        finally:
            conn.close()

    def transition(
        self,
        strategy_id: str,
        new_status: StrategyStatus,
        changed_by: str = "system",
        reason: str = "",
    ) -> bool:
        """执行状态流转。

        Returns:
            True if transition was successful, False otherwise.
        """
        current_status = self.get_status(strategy_id)

        # 检查是否允许流转
        if new_status not in VALID_TRANSITIONS.get(current_status, []):
            return False

        now = datetime.now(UTC).isoformat()

        conn = sqlite3.connect(str(self.db_path))
        try:
            # 更新当前状态
            conn.execute(
                """INSERT OR REPLACE INTO strategy_lifecycle
                   (strategy_id, status, status_changed_at, status_changed_by, reason)
                   VALUES (?, ?, ?, ?, ?)""",
                (strategy_id, new_status.value, now, changed_by, reason),
            )

            # 记录历史
            conn.execute(
                """INSERT INTO strategy_lifecycle_history
                   (strategy_id, old_status, new_status, changed_at, changed_by, reason)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (strategy_id, current_status.value, new_status.value, now, changed_by, reason),
            )

            conn.commit()
            return True
        finally:
            conn.close()

    def get_history(self, strategy_id: str) -> list[dict[str, Any]]:
        """获取策略状态变更历史。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT * FROM strategy_lifecycle_history
                   WHERE strategy_id = ?
                   ORDER BY changed_at DESC""",
                (strategy_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def list_strategies(
        self,
        status: StrategyStatus | None = None,
        limit: int = 100,
    ) -> list[StrategyLifecycle]:
        """列出策略。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            if status:
                rows = conn.execute(
                    """SELECT * FROM strategy_lifecycle
                       WHERE status = ?
                       ORDER BY status_changed_at DESC
                       LIMIT ?""",
                    (status.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM strategy_lifecycle
                       ORDER BY status_changed_at DESC
                       LIMIT ?""",
                    (limit,),
                ).fetchall()

            return [
                StrategyLifecycle(
                    strategy_id=row["strategy_id"],
                    status=StrategyStatus.from_str(row["status"]),
                    status_changed_at=row["status_changed_at"],
                    status_changed_by=row["status_changed_by"],
                    reason=row["reason"],
                    metadata={},  # TODO: 解析 metadata_json
                )
                for row in rows
            ]
        finally:
            conn.close()

    def auto_retire_check(self, strategy_id: str, excess_returns: list[float]) -> str | None:
        """检查是否需要自动退役。

        规则：
          - 连续 20 个交易日超额收益为负 → 标记 review_needed
          - 连续 40 个交易日超额收益为负 → 自动退役

        Returns:
            None if no action needed, otherwise the reason string.
        """
        if len(excess_returns) < 20:
            return None

        # 检查连续负收益天数
        consecutive_negative = 0
        for ret in reversed(excess_returns):
            if ret < 0:
                consecutive_negative += 1
            else:
                break

        if consecutive_negative >= 40:
            return f"连续 {consecutive_negative} 个交易日超额收益为负，自动退役"
        elif consecutive_negative >= 20:
            return f"连续 {consecutive_negative} 个交易日超额收益为负，需要审核"

        return None
