"""MCP Server 安全层 - 输入校验、敏感信息过滤、审计日志。"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# 敏感信息 key 列表
SECRET_KEYS = frozenset({
    "api_key", "secret_key", "passphrase", "password",
    "private_key", "access_token", "refresh_token",
    "tushare_token", "jwt_secret",
})

# 代码大小限制（50KB）
MAX_CODE_BYTES = 50 * 1024

# 审计日志路径
AUDIT_LOG_PATH = Path(__file__).resolve().parents[2] / "research_store" / "audit_log.jsonl"


def redact_secrets(value: Any, *, depth: int = 0, max_depth: int = 6) -> Any:
    """递归脱敏敏感信息。"""
    if depth > max_depth:
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if key in SECRET_KEYS and v not in (None, "", False):
                out[key] = "***"
            elif isinstance(v, dict):
                out[key] = redact_secrets(v, depth=depth + 1, max_depth=max_depth)
            elif isinstance(v, list):
                out[key] = [
                    redact_secrets(item, depth=depth + 1, max_depth=max_depth)
                    for item in v
                ]
            else:
                out[key] = v
        return out
    if isinstance(value, list):
        return [redact_secrets(item, depth=depth + 1, max_depth=max_depth) for item in value]
    return value


def assert_code_size(code: str) -> None:
    """校验代码大小不超过限制。"""
    if len((code or "").encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError(f"代码大小超过 {MAX_CODE_BYTES // 1024}KB 限制")


def assert_positive_int(name: str, value: Any, default: int = 1, max_value: int = 1000) -> int:
    """校验正整数参数。"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = default
    return max(1, min(max_value, v))


def assert_date_string(name: str, value: str) -> str:
    """校验日期字符串格式（YYYY-MM-DD）。"""
    if not value:
        return value
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        raise ValueError(f"{name} 格式错误，应为 YYYY-MM-DD")
    return value


def log_audit(action: str, detail: dict[str, Any] | None = None, result: str = "success") -> None:
    """记录审计日志。"""
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "detail": detail or {},
            "result": result,
        }
        import json
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 审计日志失败不应阻断主流程
