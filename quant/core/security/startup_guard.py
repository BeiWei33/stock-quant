"""启动守卫 - 检查配置安全性。

检查项：
  - JWT_SECRET 是否为默认值
  - 数据库路径是否为默认值
  - Web 服务绑定地址
  - 敏感配置是否存在
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class IssueSeverity(str, Enum):
    """问题严重性。"""
    ERROR = "error"      # 阻断启动
    WARNING = "warning"  # 警告但不阻断
    INFO = "info"        # 信息提示


@dataclass
class StartupIssue:
    """启动检查问题。"""
    config_key: str
    severity: IssueSeverity
    message: str
    current_value: str = ""
    recommended_value: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_key": self.config_key,
            "severity": self.severity.value,
            "message": self.message,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
        }


# 默认检查规则
DEFAULT_CHECKS = [
    {
        "config_key": "JWT_SECRET",
        "default_value": "change-me-in-production",
        "severity": IssueSeverity.ERROR,
        "message": "JWT 密钥仍为默认值，拒绝启动",
        "recommended": "请设置随机密钥：python -c \"import secrets; print(secrets.token_hex(32))\"",
    },
    {
        "config_key": "WEB_HOST",
        "default_value": "0.0.0.0",
        "severity": IssueSeverity.WARNING,
        "message": "Web 服务绑定到所有网卡，建议改为 127.0.0.1",
        "recommended": "127.0.0.1",
    },
    {
        "config_key": "DB_PATH",
        "default_value": "research_store/",
        "severity": IssueSeverity.INFO,
        "message": "数据库路径为默认值",
        "recommended": "建议使用绝对路径",
    },
]


class StartupGuard:
    """启动守卫。"""

    def __init__(self, checks: list[dict[str, Any]] | None = None):
        self.checks = checks or DEFAULT_CHECKS

    def run_checks(self, config: dict[str, Any] | None = None) -> list[StartupIssue]:
        """运行启动检查。

        Args:
            config: 配置字典，如果为 None 则从环境变量读取

        Returns:
            问题列表
        """
        issues = []

        for check in self.checks:
            config_key = check["config_key"]
            default_value = check.get("default_value", "")
            severity = check["severity"]
            message = check["message"]
            recommended = check.get("recommended", "")

            # 获取当前值
            if config:
                current_value = str(config.get(config_key, ""))
            else:
                current_value = os.environ.get(config_key, "")

            # 检查是否为默认值
            if current_value == default_value or not current_value:
                issues.append(StartupIssue(
                    config_key=config_key,
                    severity=severity,
                    message=message,
                    current_value=current_value,
                    recommended_value=recommended,
                ))

        return issues

    def check_and_raise(self, config: dict[str, Any] | None = None) -> list[StartupIssue]:
        """运行检查并在有 ERROR 时抛出异常。

        Args:
            config: 配置字典

        Returns:
            问题列表

        Raises:
            ValueError: 如果有 ERROR 级别问题
        """
        issues = self.run_checks(config)

        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        if errors:
            error_messages = [f"- {i.message}" for i in errors]
            raise ValueError(
                "启动检查失败：\n" + "\n".join(error_messages)
            )

        return issues

    def format_report(self, issues: list[StartupIssue]) -> str:
        """格式化检查报告。"""
        if not issues:
            return "✓ 启动检查通过，未发现问题"

        lines = ["启动检查报告："]
        lines.append("-" * 40)

        for issue in issues:
            icon = {
                IssueSeverity.ERROR: "✗",
                IssueSeverity.WARNING: "⚠",
                IssueSeverity.INFO: "ℹ",
            }.get(issue.severity, "?")

            lines.append(f"{icon} [{issue.severity.value.upper()}] {issue.message}")

            if issue.current_value:
                lines.append(f"  当前值: {issue.current_value}")
            if issue.recommended_value:
                lines.append(f"  建议值: {issue.recommended_value}")

        lines.append("-" * 40)

        error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)

        if error_count:
            lines.append(f"发现 {error_count} 个错误，无法启动")
        elif warning_count:
            lines.append(f"发现 {warning_count} 个警告，建议修复")

        return "\n".join(lines)


def load_config_from_yaml(config_path: Path) -> dict[str, Any]:
    """从 YAML 文件加载配置。"""
    import yaml

    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config_from_env() -> dict[str, Any]:
    """从环境变量加载配置。"""
    return {
        "JWT_SECRET": os.environ.get("JWT_SECRET", ""),
        "WEB_HOST": os.environ.get("WEB_HOST", ""),
        "DB_PATH": os.environ.get("DB_PATH", ""),
    }
