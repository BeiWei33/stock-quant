from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionDashboardPaths:
    execution_day_end: Path = Path("research_store/reports/execution_day_end.json")
    config_health: Path = Path("research_store/monitoring/config_health.json")
    readiness: Path = Path("research_store/monitoring/readiness.json")
    audit_report: Path = Path("research_store/reports/execution_audit_report.json")


@dataclass(frozen=True)
class ExecutionDashboard:
    status: str
    trade_date: str
    strategy_id: str
    html: str


def build_execution_dashboard(paths: ExecutionDashboardPaths = ExecutionDashboardPaths()) -> ExecutionDashboard:
    day_end = _read_json(paths.execution_day_end)
    config = _read_json(paths.config_health)
    readiness = _read_json(paths.readiness)
    audit = _read_json(paths.audit_report)
    status = _dashboard_status(day_end, config, readiness, audit)
    trade_date = str(day_end.get("trade_date") or audit.get("trade_date") or "")
    strategy_id = str(day_end.get("strategy_id") or audit.get("strategy_id") or "")
    return ExecutionDashboard(
        status=status,
        trade_date=trade_date,
        strategy_id=strategy_id,
        html=render_execution_dashboard_html(
            status=status,
            trade_date=trade_date,
            strategy_id=strategy_id,
            day_end=day_end,
            config=config,
            readiness=readiness,
            audit=audit,
            paths=paths,
        ),
    )


def write_execution_dashboard_html(dashboard: ExecutionDashboard, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dashboard.html, encoding="utf-8")
    return path


def render_execution_dashboard_html(
    *,
    status: str,
    trade_date: str,
    strategy_id: str,
    day_end: dict[str, Any],
    config: dict[str, Any],
    readiness: dict[str, Any],
    audit: dict[str, Any],
    paths: ExecutionDashboardPaths,
) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>Execution Dashboard</title>",
            "<style>",
            _css(),
            "</style>",
            "</head>",
            "<body>",
            '<main class="shell">',
            '<section class="hero">',
            f'<div><p class="eyebrow">Execution Control</p><h1>{_esc(status)}</h1></div>',
            f'<div class="meta"><span>{_esc(trade_date or "-")}</span><span>{_esc(strategy_id or "-")}</span></div>',
            "</section>",
            '<section class="grid four">',
            _metric("Day-End", str(day_end.get("status", "UNKNOWN")), paths.execution_day_end),
            _metric("Config", str(config.get("status", "UNKNOWN")), paths.config_health),
            _metric("Readiness", str(readiness.get("status", "UNKNOWN")), paths.readiness),
            _metric("Audit", str(audit.get("status", "UNKNOWN")), paths.audit_report),
            "</section>",
            '<section class="panel">',
            "<h2>Execution Artifacts</h2>",
            _table(
                ["Artifact", "Status", "Passed", "Detail", "Path"],
                [
                    [
                        item.get("name", ""),
                        item.get("status", ""),
                        item.get("passed", ""),
                        item.get("detail", ""),
                        item.get("path", ""),
                    ]
                    for item in day_end.get("artifacts", [])
                    if isinstance(item, dict)
                ],
            ),
            "</section>",
            '<section class="panel">',
            "<h2>Latest Audit Cycle</h2>",
            _table(
                ["Step", "Status", "Passed", "Detail"],
                [
                    [
                        item.get("event_type", ""),
                        item.get("status", ""),
                        item.get("passed", ""),
                        item.get("detail", ""),
                    ]
                    for item in audit.get("steps", [])
                    if isinstance(item, dict)
                ],
            ),
            "</section>",
            '<section class="panel">',
            "<h2>Config Checks</h2>",
            _table(
                ["Check", "Status", "Severity", "Detail"],
                [
                    [
                        item.get("name", ""),
                        item.get("status", ""),
                        item.get("severity", ""),
                        item.get("detail", ""),
                    ]
                    for item in config.get("checks", [])
                    if isinstance(item, dict)
                ],
            ),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _dashboard_status(
    day_end: dict[str, Any],
    config: dict[str, Any],
    readiness: dict[str, Any],
    audit: dict[str, Any],
) -> str:
    values = {
        str(day_end.get("status", "UNKNOWN")).upper(),
        str(config.get("status", "UNKNOWN")).upper(),
        str(audit.get("status", "UNKNOWN")).upper(),
    }
    if "ERROR" in values or "BLOCKED" in values:
        return "BLOCKED"
    if "WARNING" in values:
        return "WARNING"
    return str(readiness.get("status", "UNKNOWN")).upper()


def _metric(label: str, value: str, path: Path) -> str:
    return (
        '<div class="metric">'
        f'<span>{_esc(label)}</span>'
        f'<strong class="{_class_for_status(value)}">{_esc(value)}</strong>'
        f'<small>{_esc(str(path))}</small>'
        "</div>"
    )


def _table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return '<p class="empty">No rows.</p>'
    head = "".join(f"<th>{_esc(header)}</th>" for header in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{_esc(_cell(value))}</td>" for value in row)
        body.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _class_for_status(value: str) -> str:
    normalized = value.upper()
    if normalized in {"OK", "GO", "READY", "PAPER_READY", "LIVE_READY", "INFO"}:
        return "ok"
    if normalized in {"WARNING", "PENDING", "PENDING_MANUAL", "SKIPPED"}:
        return "warn"
    return "bad"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "MISSING", "path": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"status": "ERROR", "path": str(path)}


def _cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _css() -> str:
    return """
:root { color-scheme: light; --ink:#18212f; --muted:#667085; --line:#d8dee8; --ok:#087443; --warn:#a15c00; --bad:#b42318; --bg:#f6f8fb; --panel:#ffffff; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, sans-serif; color: var(--ink); background: var(--bg); }
.shell { width: min(1180px, calc(100% - 32px)); margin: 24px auto 48px; }
.hero { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; padding: 24px 0 18px; border-bottom: 1px solid var(--line); }
.eyebrow { margin: 0 0 8px; color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0; }
h1 { margin: 0; font-size: 42px; line-height: 1; }
h2 { margin: 0 0 14px; font-size: 18px; }
.meta { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; color: var(--muted); font-size: 14px; }
.meta span { border: 1px solid var(--line); padding: 6px 10px; border-radius: 6px; background: var(--panel); }
.grid { display: grid; gap: 12px; margin: 18px 0; }
.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.metric { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; min-width: 0; }
.metric span { display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }
.metric strong { display: block; font-size: 21px; line-height: 1.1; overflow-wrap: anywhere; }
.metric small { display: block; color: var(--muted); font-size: 12px; margin-top: 8px; overflow-wrap: anywhere; }
.ok { color: var(--ok); }
.warn { color: var(--warn); }
.bad { color: var(--bad); }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-top: 14px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; white-space: nowrap; }
td { overflow-wrap: anywhere; }
.empty { color: var(--muted); margin: 0; }
@media (max-width: 820px) { .hero { display: block; } .meta { justify-content: flex-start; margin-top: 12px; } .four { grid-template-columns: repeat(2, minmax(0, 1fr)); } h1 { font-size: 34px; } }
@media (max-width: 520px) { .four { grid-template-columns: 1fr; } }
"""
