from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    detail: str = ""


def require_non_empty(name: str, count: int) -> HealthCheck:
    return HealthCheck(name=name, ok=count > 0, detail=f"count={count}")
