"""RBAC 角色权限控制。

角色：
  - admin: 管理员，全部权限
  - operator: 操作员，可运行工作流、回测、修改策略
  - viewer: 只读用户

权限：
  - read: 读取数据
  - run_workflow: 运行工作流
  - run_backtest: 运行回测
  - edit_strategy: 修改策略
  - manage_users: 管理用户
  - view_audit: 查看审计日志
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SECURITY_DB = ROOT / "research_store" / "security.sqlite3"


class Role(str, Enum):
    """角色枚举。"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    """权限枚举。"""
    READ = "read"
    RUN_WORKFLOW = "run_workflow"
    RUN_BACKTEST = "run_backtest"
    EDIT_STRATEGY = "edit_strategy"
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT = "view_audit"


# 角色权限映射
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {
        Permission.READ,
        Permission.RUN_WORKFLOW,
        Permission.RUN_BACKTEST,
        Permission.EDIT_STRATEGY,
        Permission.MANAGE_USERS,
        Permission.VIEW_AUDIT,
    },
    Role.OPERATOR: {
        Permission.READ,
        Permission.RUN_WORKFLOW,
        Permission.RUN_BACKTEST,
        Permission.EDIT_STRATEGY,
    },
    Role.VIEWER: {
        Permission.READ,
    },
}


@dataclass
class User:
    """用户记录。"""
    user_id: str
    username: str
    role: Role
    is_active: bool = True
    created_at: str = ""
    last_login: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }


class RBACManager:
    """RBAC 管理器。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or SECURITY_DB
        self._init_db()

    def _init_db(self):
        """初始化数据库。"""
        if not self.db_path.exists():
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    role TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    last_login TEXT
                )
            """)
            conn.commit()
            conn.close()

    def create_user(
        self,
        user_id: str,
        username: str,
        role: Role = Role.VIEWER,
    ) -> User:
        """创建用户。"""
        now = datetime.now(UTC).isoformat()
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            is_active=True,
            created_at=now,
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT INTO users (user_id, username, role, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user.user_id, user.username, user.role.value, 1, user.created_at),
            )
            conn.commit()
        finally:
            conn.close()

        return user

    def get_user(self, user_id: str) -> User | None:
        """获取用户。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if not row:
                return None

            return User(
                user_id=row["user_id"],
                username=row["username"],
                role=Role(row["role"]),
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                last_login=row["last_login"],
            )
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> User | None:
        """通过用户名获取用户。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if not row:
                return None

            return User(
                user_id=row["user_id"],
                username=row["username"],
                role=Role(row["role"]),
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                last_login=row["last_login"],
            )
        finally:
            conn.close()

    def update_user_role(self, user_id: str, new_role: Role) -> User | None:
        """更新用户角色。"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE users SET role = ? WHERE user_id = ?",
                (new_role.value, user_id),
            )
            conn.commit()
        finally:
            conn.close()

        return self.get_user(user_id)

    def deactivate_user(self, user_id: str) -> bool:
        """停用用户。"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE users SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def list_users(self, role: Role | None = None) -> list[User]:
        """列出用户。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            if role:
                rows = conn.execute(
                    "SELECT * FROM users WHERE role = ? ORDER BY created_at",
                    (role.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM users ORDER BY created_at"
                ).fetchall()

            return [
                User(
                    user_id=row["user_id"],
                    username=row["username"],
                    role=Role(row["role"]),
                    is_active=bool(row["is_active"]),
                    created_at=row["created_at"],
                    last_login=row["last_login"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """检查用户是否有指定权限。"""
        user = self.get_user(user_id)
        if not user or not user.is_active:
            return False

        user_permissions = ROLE_PERMISSIONS.get(user.role, set())
        return permission in user_permissions

    def get_user_permissions(self, user_id: str) -> set[Permission]:
        """获取用户的所有权限。"""
        user = self.get_user(user_id)
        if not user or not user.is_active:
            return set()

        return ROLE_PERMISSIONS.get(user.role, set())

    def update_last_login(self, user_id: str):
        """更新最后登录时间。"""
        now = datetime.now(UTC).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE user_id = ?",
                (now, user_id),
            )
            conn.commit()
        finally:
            conn.close()
