from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


LEVEL_VALUES = {
    "INFO": 0,
    "WARNING": 1,
    "CRITICAL": 2,
    "UNKNOWN": -1,
}


@dataclass(frozen=True)
class MetricSample:
    name: str
    value: float
    help: str
    labels: dict[str, str]
    metric_type: str = "gauge"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_monitor_metrics(status_path: Path, history_path: Path | None = None) -> list[MetricSample]:
    status = _read_json(status_path)
    labels = {
        "trade_date": str(status.get("latest_trade_date", "")),
        "run_id": str(status.get("latest_run_id", "")),
    }
    level = str(status.get("level", "UNKNOWN")).upper()
    samples = [
        _sample("quant_monitor_level", _level_value(level), "Monitor level as INFO=0, WARNING=1, CRITICAL=2.", labels | {"level": level}),
        _sample("quant_monitor_latest_ok", _bool(status.get("latest_ok")), "Whether the latest daily run is OK.", labels),
        _sample("quant_monitor_success_rate", _float(status.get("success_rate")), "Success rate in the monitor window.", labels),
        _sample("quant_monitor_total_runs", _float(status.get("total_runs")), "Total runs in the monitor window.", labels),
        _sample("quant_monitor_consecutive_unhealthy_runs", _float(status.get("consecutive_unhealthy_runs")), "Trailing unhealthy run count.", labels),
        _sample("quant_monitor_total_asset", _float(status.get("latest_total_asset")), "Latest total account asset.", labels),
        _sample("quant_monitor_daily_return", _float(status.get("latest_daily_return")), "Latest daily return.", labels),
        _sample("quant_monitor_drawdown", _float(status.get("latest_drawdown")), "Latest drawdown.", labels),
        _sample("quant_monitor_max_drawdown", _float(status.get("max_drawdown")), "Maximum drawdown in the monitor window.", labels),
        _sample("quant_monitor_position_ratio", _float(status.get("latest_position_ratio")), "Latest total position ratio.", labels),
        _sample("quant_monitor_total_orders", _float(status.get("total_orders")), "Total accepted orders in the monitor window.", labels),
        _sample("quant_monitor_rejected_orders", _float(status.get("total_rejected_orders")), "Total rejected orders in the monitor window.", labels),
        _sample("quant_monitor_data_quality_issues", _float(status.get("data_quality_issue_count")), "Data quality issue count in the monitor window.", labels),
        _sample("quant_monitor_reconciliation_diffs", _float(status.get("reconciliation_diff_count")), "Reconciliation diff count in the monitor window.", labels),
        _sample("quant_monitor_risk_guard_rejected_runs", _float(status.get("risk_guard_rejected_runs")), "Risk Guard rejected run count in the monitor window.", labels),
        _sample("quant_monitor_risk_guard_rejected_orders", _float(status.get("risk_guard_rejected_orders")), "Risk Guard rejected order count in the monitor window.", labels),
        _sample("quant_monitor_pretrade_gate_passed", _bool(status.get("latest_pretrade_gate_passed")), "Whether the latest pre-trade gate passed.", labels | {"status": str(status.get("latest_pretrade_gate_status", "UNKNOWN"))}),
        _sample("quant_monitor_pretrade_gate_block_runs", _float(status.get("pretrade_gate_block_runs")), "Pre-trade gate BLOCK count in the monitor window.", labels),
        _sample("quant_monitor_failed_health_checks", _float(status.get("failed_health_count")), "Failed health check count in the monitor window.", labels),
    ]
    if history_path is not None and history_path.exists():
        history = pd.read_csv(history_path)
        samples.append(
            _sample(
                "quant_monitor_history_rows",
                float(len(history)),
                "Rows available in the monitoring history CSV.",
                {"history_path": str(history_path)},
            )
        )
    return samples


def write_metrics_json(samples: list[MetricSample], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metrics": [sample.to_dict() for sample in samples]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_prometheus_metrics(samples: list[MetricSample], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_prometheus_metrics(samples), encoding="utf-8")
    return path


def write_grafana_dashboard(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(grafana_dashboard(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_prometheus_metrics(samples: list[MetricSample]) -> str:
    lines: list[str] = []
    emitted: set[str] = set()
    for sample in samples:
        if sample.name not in emitted:
            lines.append(f"# HELP {sample.name} {_escape_help(sample.help)}")
            lines.append(f"# TYPE {sample.name} {sample.metric_type}")
            emitted.add(sample.name)
        lines.append(f"{sample.name}{_render_labels(sample.labels)} {_format_value(sample.value)}")
    return "\n".join(lines) + "\n"


def grafana_dashboard() -> dict[str, Any]:
    targets = [
        ("Monitor Level", "quant_monitor_level"),
        ("Total Asset", "quant_monitor_total_asset"),
        ("Daily Return", "quant_monitor_daily_return"),
        ("Drawdown", "quant_monitor_drawdown"),
        ("Position Ratio", "quant_monitor_position_ratio"),
        ("Pre-Trade Gate Blocks", "quant_monitor_pretrade_gate_block_runs"),
        ("Risk Guard Rejected Orders", "quant_monitor_risk_guard_rejected_orders"),
        ("Failed Health Checks", "quant_monitor_failed_health_checks"),
    ]
    panels = []
    for index, (title, expr) in enumerate(targets, start=1):
        panels.append(
            {
                "id": index,
                "type": "stat",
                "title": title,
                "gridPos": {"h": 4, "w": 6, "x": ((index - 1) % 4) * 6, "y": ((index - 1) // 4) * 4},
                "targets": [{"expr": expr, "refId": "A"}],
            }
        )
    return {
        "title": "Personal Quant Monitor",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "1m",
        "panels": panels,
    }


def _sample(name: str, value: float, help_text: str, labels: dict[str, str]) -> MetricSample:
    return MetricSample(name=name, value=value, help=help_text, labels=labels)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"monitor status not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _level_value(level: str) -> float:
    return float(LEVEL_VALUES.get(level, LEVEL_VALUES["UNKNOWN"]))


def _bool(value: object) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return 1.0 if str(value).strip().lower() in {"1", "true", "yes"} else 0.0


def _float(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _render_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    values = ",".join(f'{key}="{_escape_label(value)}"' for key, value in sorted(labels.items()))
    return "{" + values + "}"


def _escape_label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _escape_help(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n")


def _format_value(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.12g}"
