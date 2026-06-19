from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class NotificationMessage:
    title: str
    level: str
    trade_date: str
    status: str
    body: str
    summary_path: str
    report_markdown_path: str = ""
    report_html_path: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class DailyNotificationBuilder:
    """Build a compact notification from a daily workflow summary."""

    def __init__(
        self,
        *,
        summary_path: Path,
        report_markdown_path: Path | None = None,
        report_html_path: Path | None = None,
    ) -> None:
        self.summary_path = summary_path
        self.report_markdown_path = report_markdown_path
        self.report_html_path = report_html_path

    def build(self) -> NotificationMessage:
        summary = _read_json(self.summary_path)
        trade_date = _trade_date(summary)
        status = str(summary.get("run_status", "UNKNOWN"))
        level = _level(summary)
        snapshot = summary.get("snapshot") if isinstance(summary.get("snapshot"), dict) else {}
        failed_checks = _failed_health_checks(summary.get("health_checks", []))
        title = f"[{level}] Quant Daily {trade_date} {status}"
        body = _body(summary, snapshot, failed_checks)
        return NotificationMessage(
            title=title,
            level=level,
            trade_date=trade_date,
            status=status,
            body=body,
            summary_path=str(self.summary_path),
            report_markdown_path=str(self.report_markdown_path or ""),
            report_html_path=str(self.report_html_path or ""),
        )


class FileNotificationSink:
    """Persist the latest notification for local audit and scheduler pickup."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path

    def send(self, message: NotificationMessage) -> Path:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = message.to_dict()
        payload["text"] = render_text(message)
        self.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.output_path


def render_text(message: NotificationMessage) -> str:
    lines = [
        message.title,
        "",
        message.body,
        "",
        f"Summary: {message.summary_path}",
    ]
    if message.report_markdown_path:
        lines.append(f"Markdown Report: {message.report_markdown_path}")
    if message.report_html_path:
        lines.append(f"HTML Report: {message.report_html_path}")
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"daily summary not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _trade_date(summary: dict[str, Any]) -> str:
    value = summary.get("trade_date")
    if not value:
        return "-"
    return pd.to_datetime(value).date().isoformat()


def _level(summary: dict[str, Any]) -> str:
    status = str(summary.get("run_status", "")).upper()
    if status == "FAILED":
        return "CRITICAL"
    if status in {"CHECK", "WARNING"}:
        return "WARNING"
    if not bool(summary.get("ok", False)):
        return "WARNING"
    if _failed_health_checks(summary.get("health_checks", [])):
        return "WARNING"
    return "INFO"


def _failed_health_checks(checks: object) -> list[dict[str, Any]]:
    if not isinstance(checks, list):
        return []
    failed = []
    for check in checks:
        if isinstance(check, dict) and not bool(check.get("ok", False)):
            failed.append(check)
    return failed


def _body(
    summary: dict[str, Any],
    snapshot: dict[str, Any],
    failed_checks: list[dict[str, Any]],
) -> str:
    lines = [
        f"Run ID: {summary.get('run_id', '-')}",
        f"Orders: {summary.get('order_count', 0)} accepted, {summary.get('rejected_order_count', 0)} rejected",
        f"Fills: {summary.get('fill_count', 0)} filled, {summary.get('fill_rejected_count', 0)} rejected",
        f"Data: {summary.get('collected_stocks', 0)} stocks, {summary.get('collected_daily_bars', 0)} daily bars",
        f"Data Quality: {summary.get('data_quality_level', '-')}",
    ]
    if summary.get("data_quality_markdown_path"):
        lines.append(f"Data Quality Report: {summary.get('data_quality_markdown_path')}")
    if snapshot:
        lines.extend(
            [
                f"Total Asset: {_money(snapshot.get('total_asset'))}",
                f"Cash: {_money(snapshot.get('cash'))}",
                f"Market Value: {_money(snapshot.get('market_value'))}",
                f"Position Ratio: {_percent(snapshot.get('total_position_ratio'))}",
                f"Daily Return: {_percent(snapshot.get('daily_return'))}",
                f"Drawdown: {_percent(snapshot.get('drawdown'))}",
            ]
        )
    if summary.get("error_msg"):
        lines.append(f"Error: {summary.get('error_msg')}")
    if failed_checks:
        lines.append("Failed Health Checks:")
        lines.extend(
            f"- {check.get('name', '-')}: {check.get('detail', '')}" for check in failed_checks
        )
    return "\n".join(lines)


def _money(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.2f}"


def _percent(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.2f}%"
