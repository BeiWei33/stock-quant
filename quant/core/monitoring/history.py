from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DailyMonitorRecord:
    recorded_at: str
    trade_date: str
    run_id: str
    run_status: str
    ok: bool
    collected_stocks: int
    collected_daily_bars: int
    collected_benchmark_bars: int
    order_count: int
    rejected_order_count: int
    fill_count: int
    fill_rejected_count: int
    total_asset: float
    cash: float
    market_value: float
    total_position_ratio: float
    daily_return: float
    cum_return: float
    drawdown: float
    excess_return: float
    data_quality_level: str
    data_quality_ok: bool
    data_quality_issue_count: int
    data_quality_error_count: int
    data_quality_warning_count: int
    data_cleaning_changed_rows: int
    data_cleaning_high_fixed_count: int
    data_cleaning_low_fixed_count: int
    reconciliation_status: str
    reconciliation_diff_count: int
    reconciliation_order_diff_count: int
    reconciliation_fill_diff_count: int
    risk_guard_status: str
    risk_guard_allowed: bool
    risk_guard_input_orders: int
    risk_guard_rejected_orders: int
    risk_guard_epoch_seconds: int
    pretrade_gate_status: str
    pretrade_gate_passed: bool
    pretrade_gate_failed_count: int
    pretrade_gate_failed_checks: str
    failed_health_count: int
    failed_health_checks: str
    summary_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DailyMonitorRecordBuilder:
    def __init__(
        self,
        summary_path: Path,
        cleaning_report_path: Path | None = None,
        reconciliation_report_path: Path | None = None,
        risk_guard_audit_path: Path | None = None,
        pretrade_gate_report_path: Path | None = None,
    ) -> None:
        self.summary_path = summary_path
        self.cleaning_report_path = cleaning_report_path
        self.reconciliation_report_path = reconciliation_report_path
        self.risk_guard_audit_path = risk_guard_audit_path
        self.pretrade_gate_report_path = pretrade_gate_report_path

    def build(self) -> DailyMonitorRecord:
        summary = _read_json(self.summary_path)
        snapshot = summary.get("snapshot") if isinstance(summary.get("snapshot"), dict) else {}
        failed_checks = _failed_health_checks(summary.get("health_checks", []))
        quality = _read_optional_json(_resolve_path(summary.get("data_quality_json_path")))
        cleaning = _read_optional_json(
            self.cleaning_report_path
            or _default_cleaning_report_path(self.summary_path, summary.get("data_cleaning_json_path"))
        )
        reconciliation = _read_optional_json(
            self.reconciliation_report_path
            or _resolve_path(summary.get("trade_reconciliation_json_path"))
            or _resolve_path(summary.get("reconciliation_json_path"))
        )
        reconciliation_counts = _reconciliation_counts(reconciliation)
        risk_guard = _latest_risk_guard_run(self.risk_guard_audit_path)
        pretrade_gate = _read_optional_json(self.pretrade_gate_report_path)
        pretrade_gate_failed_checks = _failed_pretrade_gate_checks(pretrade_gate)
        quality_issues = quality.get("issues", []) if isinstance(quality.get("issues", []), list) else []
        quality_error_count = sum(
            1 for issue in quality_issues if isinstance(issue, dict) and issue.get("severity") == "ERROR"
        )
        quality_warning_count = sum(
            1 for issue in quality_issues if isinstance(issue, dict) and issue.get("severity") == "WARNING"
        )
        return DailyMonitorRecord(
            recorded_at=datetime.now(UTC).isoformat(),
            trade_date=_trade_date(summary),
            run_id=str(summary.get("run_id", "")),
            run_status=str(summary.get("run_status", "UNKNOWN")),
            ok=bool(summary.get("ok", False)),
            collected_stocks=_int(summary.get("collected_stocks")),
            collected_daily_bars=_int(summary.get("collected_daily_bars")),
            collected_benchmark_bars=_int(summary.get("collected_benchmark_bars")),
            order_count=_int(summary.get("order_count")),
            rejected_order_count=_int(summary.get("rejected_order_count")),
            fill_count=_int(summary.get("fill_count")),
            fill_rejected_count=_int(summary.get("fill_rejected_count")),
            total_asset=_float(snapshot.get("total_asset")),
            cash=_float(snapshot.get("cash")),
            market_value=_float(snapshot.get("market_value")),
            total_position_ratio=_float(snapshot.get("total_position_ratio")),
            daily_return=_float(snapshot.get("daily_return")),
            cum_return=_float(snapshot.get("cum_return")),
            drawdown=_float(snapshot.get("drawdown")),
            excess_return=_float(snapshot.get("excess_return")),
            data_quality_level=str(summary.get("data_quality_level", quality.get("level", "UNKNOWN"))),
            data_quality_ok=bool(quality.get("ok", summary.get("data_quality_level", "") == "INFO")),
            data_quality_issue_count=len(quality_issues),
            data_quality_error_count=quality_error_count,
            data_quality_warning_count=quality_warning_count,
            data_cleaning_changed_rows=_int(cleaning.get("changed_rows", cleaning.get("changed_row_count"))),
            data_cleaning_high_fixed_count=_int(cleaning.get("high_fixed_count")),
            data_cleaning_low_fixed_count=_int(cleaning.get("low_fixed_count")),
            reconciliation_status=str(reconciliation.get("status", "UNKNOWN")),
            reconciliation_diff_count=reconciliation_counts["total"],
            reconciliation_order_diff_count=reconciliation_counts["orders"],
            reconciliation_fill_diff_count=reconciliation_counts["fills"],
            risk_guard_status=_risk_guard_status(risk_guard),
            risk_guard_allowed=bool(risk_guard.get("allowed", False)) if risk_guard else False,
            risk_guard_input_orders=_int(risk_guard.get("input_orders")) if risk_guard else 0,
            risk_guard_rejected_orders=_int(risk_guard.get("rejected_orders")) if risk_guard else 0,
            risk_guard_epoch_seconds=_int(risk_guard.get("epoch_seconds")) if risk_guard else 0,
            pretrade_gate_status=str(pretrade_gate.get("status", "UNKNOWN")).upper(),
            pretrade_gate_passed=bool(pretrade_gate.get("passed", False)) if pretrade_gate else False,
            pretrade_gate_failed_count=len(pretrade_gate_failed_checks),
            pretrade_gate_failed_checks=";".join(str(check.get("name", "")) for check in pretrade_gate_failed_checks),
            failed_health_count=len(failed_checks),
            failed_health_checks=";".join(str(check.get("name", "")) for check in failed_checks),
            summary_path=str(self.summary_path),
        )


class DailyMonitorCsvStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def upsert(self, record: DailyMonitorRecord) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = record.to_dict()
        if self.path.exists():
            df = pd.read_csv(self.path)
            if "run_id" in df.columns and record.run_id:
                df = df[df["run_id"].astype(str) != record.run_id]
            else:
                df = df[df["trade_date"].astype(str) != record.trade_date]
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        df = df.sort_values(["trade_date", "run_id"]).reset_index(drop=True)
        temp_path = self.path.with_name(f".{self.path.name}.tmp")
        df.to_csv(temp_path, index=False)
        temp_path.replace(self.path)
        return self.path


class DailyMonitorJsonlStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: DailyMonitorRecord) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return self.path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"daily summary not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _read_optional_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _resolve_path(value: object) -> Path | None:
    if not value:
        return None
    return Path(str(value))


def _default_cleaning_report_path(summary_path: Path, value: object) -> Path:
    if value:
        return Path(str(value))
    return summary_path.parent / "data_cleaning.json"


def _reconciliation_counts(report: dict[str, Any]) -> dict[str, int]:
    if not report:
        return {"total": 0, "orders": 0, "fills": 0}
    order_differences = report.get("order_differences")
    fill_differences = report.get("fill_differences")
    differences = report.get("differences")
    order_count = len(order_differences) if isinstance(order_differences, list) else 0
    fill_count = len(fill_differences) if isinstance(fill_differences, list) else 0
    if order_count or fill_count:
        return {"total": order_count + fill_count, "orders": order_count, "fills": fill_count}
    total = len(differences) if isinstance(differences, list) else 0
    return {"total": total, "orders": 0, "fills": 0}


def _latest_risk_guard_run(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    latest: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event_type") == "RiskGuardRun":
            latest = event
    return latest


def _risk_guard_status(event: dict[str, Any]) -> str:
    if not event:
        return "UNKNOWN"
    if bool(event.get("allowed", False)):
        return "OK"
    return "REJECTED"


def _trade_date(summary: dict[str, Any]) -> str:
    value = summary.get("trade_date")
    if not value:
        return ""
    return pd.to_datetime(value).date().isoformat()


def _failed_health_checks(checks: object) -> list[dict[str, Any]]:
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, dict) and not bool(check.get("ok", False))]


def _failed_pretrade_gate_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks = report.get("checks", [])
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, dict) and not bool(check.get("passed", False))]


def _int(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


def _float(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)
