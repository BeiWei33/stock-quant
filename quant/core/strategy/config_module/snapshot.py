"""策略快照管理 - 不可变的策略配置记录。

每次策略配置变更时生成快照，用于：
  - 版本追溯
  - 回测复现
  - 审核记录
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import StrategyConfig

DB_PATH = Path("research_store/strategy_snapshots.sqlite3")


@dataclass(frozen=True)
class StrategySnapshot:
    """策略快照 - 不可变记录。"""
    snapshot_id: str              # 快照ID
    strategy_id: str              # 策略ID
    strategy_version: str         # 策略版本
    config: StrategyConfig        # 完整配置
    config_hash: str              # 配置哈希（用于去重）
    code_hash: str                # 代码哈希
    backtest_summary: dict[str, Any]  # 回测摘要
    created_at: str               # 创建时间
    created_by: str               # 创建者

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "config": self.config.to_dict(),
            "config_hash": self.config_hash,
            "code_hash": self.code_hash,
            "backtest_summary": self.backtest_summary,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


class StrategySnapshotStore:
    """策略快照存储。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self):
        """初始化数据库表。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    code_hash TEXT DEFAULT '',
                    backtest_summary_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    created_by TEXT DEFAULT 'system'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_strategy_id
                ON strategy_snapshots(strategy_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_config_hash
                ON strategy_snapshots(config_hash)
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, snapshot: StrategySnapshot) -> None:
        """保存快照。"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT OR REPLACE INTO strategy_snapshots
                   (snapshot_id, strategy_id, strategy_version, config_json,
                    config_hash, code_hash, backtest_summary_json, created_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.snapshot_id,
                    snapshot.strategy_id,
                    snapshot.strategy_version,
                    snapshot.config.to_json(),
                    snapshot.config_hash,
                    snapshot.code_hash,
                    json.dumps(snapshot.backtest_summary),
                    snapshot.created_at,
                    snapshot.created_by,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, snapshot_id: str) -> StrategySnapshot | None:
        """获取快照。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM strategy_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_snapshot(row)
        finally:
            conn.close()

    def list_by_strategy(self, strategy_id: str, limit: int = 50) -> list[StrategySnapshot]:
        """列出策略的所有快照。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT * FROM strategy_snapshots
                   WHERE strategy_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (strategy_id, limit),
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]
        finally:
            conn.close()

    def find_by_hash(self, config_hash: str) -> StrategySnapshot | None:
        """通过配置哈希查找快照。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM strategy_snapshots WHERE config_hash = ?",
                (config_hash,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_snapshot(row)
        finally:
            conn.close()

    def _row_to_snapshot(self, row: sqlite3.Row) -> StrategySnapshot:
        """将数据库行转换为快照对象。"""
        return StrategySnapshot(
            snapshot_id=row["snapshot_id"],
            strategy_id=row["strategy_id"],
            strategy_version=row["strategy_version"],
            config=StrategyConfig.from_json(row["config_json"]),
            config_hash=row["config_hash"],
            code_hash=row["code_hash"],
            backtest_summary=json.loads(row["backtest_summary_json"]),
            created_at=row["created_at"],
            created_by=row["created_by"],
        )


def compute_config_hash(config: StrategyConfig) -> str:
    """计算配置哈希。"""
    config_json = config.to_json()
    return hashlib.sha256(config_json.encode()).hexdigest()[:16]


def create_snapshot(
    config: StrategyConfig,
    backtest_summary: dict[str, Any] | None = None,
    created_by: str = "system",
) -> StrategySnapshot:
    """创建策略快照。"""
    now = datetime.now(UTC).isoformat()
    config_hash = compute_config_hash(config)

    return StrategySnapshot(
        snapshot_id=f"snap_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{config_hash[:8]}",
        strategy_id=config.strategy_id,
        strategy_version=config.strategy_version,
        config=config,
        config_hash=config_hash,
        code_hash="",  # TODO: 计算代码哈希
        backtest_summary=backtest_summary or {},
        created_at=now,
        created_by=created_by,
    )
