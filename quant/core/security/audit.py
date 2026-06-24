"""审计日志 - 记录关键操作。

记录的操作：
  - 用户登录/登出
  - 运行工作流
  - 运行回测
  - 修改策略
  - 管理用户
  - 查看审计日志
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SECURITY_DB = ROOT / "research_store" / "security.sqlite3"
AUDIT_LOG_FILE = ROOT / "research_store" / "audit_log.jsonl"


@dataclass
class AuditEntry:
    """审计日志条目。"""
    entry_id: str
    timestamp: str
    user_id: str
    username: str
    action: str
    target: str
    detail: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    result: str = "success"  # success / denied / error

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "target": self.target,
            "detail": self.detail,
            "ip_address": self.ip_address,
            "result": self.result,
        }


class AuditLogger:
    """审计日志记录器。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or SECURITY_DB
        self._init_db()

    def _init_db(self):
        """初始化数据库。"""
        if not self.db_path.exists():
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    entry_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    user_id TEXT,
                    username TEXT,
                    action TEXT,
                    target TEXT,
                    detail TEXT,
                    ip_address TEXT,
                    result TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user
                ON audit_log(user_id, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_action
                ON audit_log(action, timestamp)
            """)
            conn.commit()
            conn.close()

    def log(
        self,
        user_id: str,
        username: str,
        action: str,
        target: str = "",
        detail: dict[str, Any] | None = None,
        ip_address: str = "",
        result: str = "success",
    ) -> AuditEntry:
        """记录审计日志。

        Args:
            user_id: 用户 ID
            username: 用户名
            action: 操作类型
            target: 操作目标
            detail: 详细信息
            ip_address: IP 地址
            result: 结果（success / denied / error）

        Returns:
            审计日志条目
        """
        timestamp = datetime.now(UTC).isoformat()
        entry_id = f"audit_{timestamp}_{user_id}"

        entry = AuditEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            user_id=user_id,
            username=username,
            action=action,
            target=target,
            detail=detail or {},
            ip_address=ip_address,
            result=result,
        )

        # 保存到数据库
        self._save_to_db(entry)

        # 同时写入文件（备份）
        self._save_to_file(entry)

        return entry

    def _save_to_db(self, entry: AuditEntry):
        """保存到数据库。"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT INTO audit_log
                   (entry_id, timestamp, user_id, username, action,
                    target, detail, ip_address, result)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.entry_id,
                    entry.timestamp,
                    entry.user_id,
                    entry.username,
                    entry.action,
                    entry.target,
                    json.dumps(entry.detail),
                    entry.ip_address,
                    entry.result,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _save_to_file(self, entry: AuditEntry):
        """保存到文件（备份）。"""
        try:
            AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass  # 文件写入失败不应阻断主流程

    def query(
        self,
        user_id: str | None = None,
        action: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """查询审计日志。

        Args:
            user_id: 用户 ID
            action: 操作类型
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回条数

        Returns:
            审计日志列表
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM audit_log WHERE 1=1"
            params: list[Any] = []

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            if action:
                query += " AND action = ?"
                params.append(action)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

            return [
                AuditEntry(
                    entry_id=row["entry_id"],
                    timestamp=row["timestamp"],
                    user_id=row["user_id"],
                    username=row["username"],
                    action=row["action"],
                    target=row["target"],
                    detail=json.loads(row["detail"]),
                    ip_address=row["ip_address"],
                    result=row["result"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_user_actions(
        self, user_id: str, limit: int = 50
    ) -> list[AuditEntry]:
        """获取用户的操作记录。"""
        return self.query(user_id=user_id, limit=limit)

    def get_action_stats(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, int]:
        """获取操作统计。"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT action, COUNT(*) as cnt FROM audit_log WHERE 1=1"
            params: list[Any] = []

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " GROUP BY action ORDER BY cnt DESC"

            rows = conn.execute(query, params).fetchall()
            return {row[0]: row[1] for row in rows}
        finally:
            conn.close()

    def get_recent_entries(self, limit: int = 20) -> list[AuditEntry]:
        """获取最近的审计日志。"""
        return self.query(limit=limit)
