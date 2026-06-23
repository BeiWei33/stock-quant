"""Common Pydantic models for API responses."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope."""
    code: int = 200
    message: str = "ok"
    data: T | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""
    code: int = 200
    message: str = "ok"
    data: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    """Error response."""
    code: int
    message: str
    detail: Any = None


class StatusCard(BaseModel):
    """Dashboard status card."""
    label: str
    value: str
    status: str = "ok"  # ok, warning, error
    detail: str | None = None


class MetricValue(BaseModel):
    """Metric with label and value."""
    label: str
    value: float
    format: str = "number"  # number, percent, currency
    change: float | None = None
    change_format: str | None = None
