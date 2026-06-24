"""策略快照系统 - 不可变的策略版本记录。

每次策略变更都会生成一个快照，包含：
  - 策略代码哈希
  - 配置哈希
  - 回测摘要
  - 因子集合
  - 创建时间
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
LIFECYCLE_DB = ROOT / "research_store" / "strategy_lifecycle.sqlite3"


@dataclass(frozen=True)
class StrategySnapshot:
    """策略快照（不可变）。"""
    snapshot_id: str
    strategy_id: str
    strategy_version: str
    code_hash: str
    config_hash: str
    backtest_summary: dict[str, Any] = field(default_factory=dict)
    factor_set: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "code_hash": self.code_hash,
            "config_hash": self.config_hash,
            "backtest_summary": self.backtest_summary,
            "factor_set": self.factor_set,
            "created_at": self.created_at,
        }


class StrategySnapshotStore:
    """策略快照存储。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or LIFECYCLE_DB
        self._init_db()

    def _init_db(self):
        """初始化数据库。"""
        if not self.db_path.exists():
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    strategy_id TEXT,
                    strategy_version TEXT,
                    code_hash TEXT,
                    config_hash TEXT,
                    backtest_summary TEXT,
                    factor_set TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_strategy
                ON strategy_snapshots(strategy_id, created_at)
            """)
            conn.commit()
            conn.close()

    def save_snapshot(
        self,
        strategy_id: str,
        strategy_version: str,
        code: str,
        config: dict[str, Any],
        backtest_summary: dict[str, Any] | None = None,
        factor_set: list[str] | None = None,
    ) -> StrategySnapshot:
        """保存策略快照。

        Args:
            strategy_id: 策略 ID
            strategy_version: 策略版本
            code: 策略代码
            config: 策略配置
            backtest_summary: 回测摘要
            factor_set: 因子集合

        Returns:
            策略快照
        """
        # 计算哈希
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        config_str = json.dumps(config, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]

        # 生成快照 ID
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        snapshot_id = f"snap_{strategy_id}_{timestamp}"

        # 创建快照
        snapshot = StrategySnapshot(
            snapshot_id=snapshot_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            code_hash=code_hash,
            config_hash=config_hash,
            backtest_summary=backtest_summary or {},
            factor_set=factor_set or [],
            created_at=datetime.now(UTC).isoformat(),
        )

        # 保存到数据库
        self._save_to_db(snapshot)

        return snapshot

    def _save_to_db(self, snapshot: StrategySnapshot):
        """保存快照到数据库。"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT INTO strategy_snapshots
                   (snapshot_id, strategy_id, strategy_version, code_hash,
                    config_hash, backtest_summary, factor_set, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.snapshot_id,
                    snapshot.strategy_id,
                    snapshot.strategy_version,
                    snapshot.code_hash,
                    snapshot.config_hash,
                    json.dumps(snapshot.backtest_summary),
                    json.dumps(snapshot.factor_set),
                    snapshot.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_snapshot(self, snapshot_id: str) -> StrategySnapshot | None:
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

            return StrategySnapshot(
                snapshot_id=row["snapshot_id"],
                strategy_id=row["strategy_id"],
                strategy_version=row["strategy_version"],
                code_hash=row["code_hash"],
                config_hash=row["config_hash"],
                backtest_summary=json.loads(row["backtest_summary"]),
                factor_set=json.loads(row["factor_set"]),
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def list_snapshots(
        self,
        strategy_id: str | None = None,
        limit: int = 20,
    ) -> list[StrategySnapshot]:
        """列出快照。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            if strategy_id:
                rows = conn.execute(
                    """SELECT * FROM strategy_snapshots
                       WHERE strategy_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (strategy_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM strategy_snapshots ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            return [
                StrategySnapshot(
                    snapshot_id=row["snapshot_id"],
                    strategy_id=row["strategy_id"],
                    strategy_version=row["strategy_version"],
                    code_hash=row["code_hash"],
                    config_hash=row["config_hash"],
                    backtest_summary=json.loads(row["backtest_summary"]),
                    factor_set=json.loads(row["factor_set"]),
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_latest_snapshot(self, strategy_id: str) -> StrategySnapshot | None:
        """获取策略的最新快照。"""
        snapshots = self.list_snapshots(strategy_id, limit=1)
        return snapshots[0] if snapshots else None

    def compare_snapshots(
        self, snapshot_id_1: str, snapshot_id_2: str
    ) -> dict[str, Any]:
        """对比两个快照。"""
        snap1 = self.get_snapshot(snapshot_id_1)
        snap2 = self.get_snapshot(snapshot_id_2)

        if not snap1 or not snap2:
            return {"error": "快照不存在"}

        diff = {
            "snapshot_1": snap1.to_dict(),
            "snapshot_2": snap2.to_dict(),
            "code_changed": snap1.code_hash != snap2.code_hash,
            "config_changed": snap1.config_hash != snap2.config_hash,
            "factor_set_changed": set(snap1.factor_set) != set(snap2.factor_set),
        }

        # 对比回测指标
        if snap1.backtest_summary and snap2.backtest_summary:
            diff["metrics_diff"] = {}
            for key in ["sharpe", "annual_return", "max_drawdown"]:
                v1 = snap1.backtest_summary.get(key, 0)
                v2 = snap2.backtest_summary.get(key, 0)
                diff["metrics_diff"][key] = {
                    "before": v1,
                    "after": v2,
                    "change": v2 - v1,
                }

        return diff
