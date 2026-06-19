from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from quant.core.monitoring.alerts import evaluate_monitor_alerts, write_alerts_json, write_alerts_markdown
from quant.core.monitoring.metrics import (
    build_monitor_metrics,
    write_grafana_dashboard,
    write_metrics_json,
    write_prometheus_metrics,
)
from quant.core.monitoring.readiness import (
    build_readiness_report,
    write_readiness_json,
    write_readiness_markdown,
)
from quant.core.monitoring.stability import (
    StabilityReportBuilder,
    write_stability_json,
    write_stability_markdown,
)
from quant.core.monitoring.status import MonitorStatusBuilder, write_status_json, write_status_markdown


@dataclass(frozen=True)
class MonitorRefreshPaths:
    history: Path = Path("research_store/monitoring/daily_history.csv")
    pretrade_gate: Path = Path("research_store/reports/pretrade_gate.json")
    status_json: Path = Path("research_store/monitoring/status_summary.json")
    status_md: Path = Path("research_store/monitoring/status_summary.md")
    alerts_json: Path = Path("research_store/monitoring/alerts.json")
    alerts_md: Path = Path("research_store/monitoring/alerts.md")
    metrics_prom: Path = Path("research_store/monitoring/metrics.prom")
    metrics_json: Path = Path("research_store/monitoring/metrics.json")
    grafana_dashboard: Path = Path("research_store/monitoring/grafana_dashboard.json")
    stability_json: Path = Path("research_store/monitoring/stability.json")
    stability_md: Path = Path("research_store/monitoring/stability.md")
    readiness_json: Path = Path("research_store/monitoring/readiness.json")
    readiness_md: Path = Path("research_store/monitoring/readiness.md")


@dataclass(frozen=True)
class MonitorRefreshResult:
    level: str
    alerts_status: str
    readiness_status: str
    stability_status: str
    written_paths: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def refresh_monitoring(
    paths: MonitorRefreshPaths,
    *,
    limit: int = 20,
    target_days: int = 20,
    qmt_available: bool = False,
    write_dashboard: bool = True,
) -> MonitorRefreshResult:
    status = MonitorStatusBuilder(paths.history, limit=limit).build()
    write_status_json(status, paths.status_json)
    write_status_markdown(status, paths.status_md)

    alerts = evaluate_monitor_alerts(paths.status_json)
    write_alerts_json(alerts, paths.alerts_json)
    write_alerts_markdown(alerts, paths.alerts_md)

    samples = build_monitor_metrics(paths.status_json, history_path=paths.history)
    write_prometheus_metrics(samples, paths.metrics_prom)
    write_metrics_json(samples, paths.metrics_json)
    if write_dashboard:
        write_grafana_dashboard(paths.grafana_dashboard)

    stability = StabilityReportBuilder(paths.history, target_days=target_days).build()
    write_stability_json(stability, paths.stability_json)
    write_stability_markdown(stability, paths.stability_md)

    readiness = build_readiness_report(
        alerts_path=paths.alerts_json,
        pretrade_gate_path=paths.pretrade_gate,
        stability_path=paths.stability_json,
        qmt_available=qmt_available,
    )
    write_readiness_json(readiness, paths.readiness_json)
    write_readiness_markdown(readiness, paths.readiness_md)

    written_paths = {
        "status_json": str(paths.status_json),
        "status_md": str(paths.status_md),
        "alerts_json": str(paths.alerts_json),
        "alerts_md": str(paths.alerts_md),
        "metrics_prom": str(paths.metrics_prom),
        "metrics_json": str(paths.metrics_json),
        "stability_json": str(paths.stability_json),
        "stability_md": str(paths.stability_md),
        "readiness_json": str(paths.readiness_json),
        "readiness_md": str(paths.readiness_md),
    }
    if write_dashboard:
        written_paths["grafana_dashboard"] = str(paths.grafana_dashboard)
    return MonitorRefreshResult(
        level=status.level,
        alerts_status=alerts.status,
        readiness_status=readiness.status,
        stability_status=stability.status,
        written_paths=written_paths,
    )
