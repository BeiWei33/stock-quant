from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ConfigHealthCheck:
    name: str
    status: str
    severity: str
    path: str
    detail: str

    @property
    def passed(self) -> bool:
        return self.severity == "INFO"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["passed"] = self.passed
        return data


@dataclass(frozen=True)
class ConfigHealthReport:
    status: str
    error_count: int
    warning_count: int
    checks: list[ConfigHealthCheck]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class ConfigHealthPaths:
    stocks: Path = Path("research_store/sample/stocks.csv")
    bars: Path = Path("research_store/sample/daily_bar.cleaned.csv")
    daily_config: Path = Path("config/daily.yaml")
    cleaning_config: Path = Path("config/cleaning.yaml")
    risk_guard_control: Path = Path("research_store/state/risk_guard_control.env")
    execution_policy: Path = Path("config/execution_policy.generated.json")
    broker_submission: Path = Path("research_store/reports/broker_submission.json")
    execution_authorization: Path = Path("research_store/reports/execution_authorization.json")
    broker_adapter_contract: Path = Path("research_store/reports/broker_adapter_contract.json")
    pretrade_gate: Path = Path("research_store/reports/pretrade_gate.json")
    manual_order_ticket: Path = Path("research_store/reports/manual_order_ticket.csv")
    manual_fill_template: Path = Path("research_store/reports/manual_fill_template.csv")
    manual_fill_validation: Path = Path("research_store/reports/manual_fill_validation.json")
    execution_day_end: Path = Path("research_store/reports/execution_day_end.json")
    monitor_status: Path = Path("research_store/monitoring/status_summary.json")
    readiness: Path = Path("research_store/monitoring/readiness.json")
    history: Path = Path("research_store/monitoring/daily_history.csv")


def build_config_health_report(paths: ConfigHealthPaths) -> ConfigHealthReport:
    checks = [
        _csv_check("stocks", paths.stocks, {"ts_code", "name", "exchange"}),
        _csv_check("daily_bars", paths.bars, {"ts_code", "trade_date", "open", "high", "low", "close", "volume", "amount"}),
        _file_check("daily_config", paths.daily_config),
        _file_check("cleaning_config", paths.cleaning_config),
        _risk_control_check(paths.risk_guard_control),
        _execution_policy_check(paths.execution_policy),
        _json_fields_check("broker_submission", paths.broker_submission, {"mode", "adapter", "trade_date", "strategy_id", "order_count", "orders"}),
        _json_status_check("execution_authorization", paths.execution_authorization, status_key="status", ok_values={"GO"}),
        _broker_adapter_contract_check(paths.broker_adapter_contract),
        _json_status_check("pretrade_gate", paths.pretrade_gate, status_key="status", ok_values={"GO"}),
        _csv_check("manual_order_ticket", paths.manual_order_ticket, {"trade_date", "ts_code", "side", "quantity", "limit_price", "order_id", "broker_order_id"}),
        _csv_check("manual_fill_template", paths.manual_fill_template, {"trade_date", "ts_code", "side", "quantity", "price", "amount", "order_id", "broker_order_id", "status"}),
        _manual_validation_check(paths.manual_fill_validation),
        _json_status_check("execution_day_end", paths.execution_day_end, status_key="status", ok_values={"READY"}, warning_values={"PENDING_MANUAL", "BLOCKED"}),
        _json_status_check("monitor_status", paths.monitor_status, status_key="level", ok_values={"INFO"}, warning_values={"WARNING"}),
        _json_status_check("readiness", paths.readiness, status_key="status", ok_values={"LIVE_READY", "PAPER_READY"}, warning_values={"BLOCKED"}),
        _csv_check("monitor_history", paths.history, {"trade_date", "run_id", "run_status", "ok"}),
    ]
    error_count = sum(1 for check in checks if check.severity == "ERROR")
    warning_count = sum(1 for check in checks if check.severity == "WARNING")
    status = "ERROR" if error_count else "WARNING" if warning_count else "OK"
    return ConfigHealthReport(
        status=status,
        error_count=error_count,
        warning_count=warning_count,
        checks=checks,
    )


def write_config_health_json(report: ConfigHealthReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_config_health_markdown(report: ConfigHealthReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_config_health_markdown(report), encoding="utf-8")
    return path


def render_config_health_markdown(report: ConfigHealthReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Errors", report.error_count],
        ["Warnings", report.warning_count],
        ["Checks", len(report.checks)],
    ]
    check_rows = [
        [check.name, check.status, check.severity, check.detail, check.path]
        for check in report.checks
    ]
    return "\n".join(
        [
            "# Config Health Report",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Checks",
            _table(["Check", "Status", "Severity", "Detail", "Path"], check_rows),
            "",
        ]
    )


def _file_check(name: str, path: Path) -> ConfigHealthCheck:
    if not path.exists():
        return _check(name, path, "MISSING", "ERROR", "file not found")
    if path.stat().st_size <= 0:
        return _check(name, path, "EMPTY", "ERROR", "file is empty")
    return _check(name, path, "OK", "INFO", f"bytes={path.stat().st_size}")


def _csv_check(name: str, path: Path, required_columns: set[str]) -> ConfigHealthCheck:
    base = _file_check(name, path)
    if not base.passed:
        return base
    try:
        df = pd.read_csv(path, nrows=5)
    except Exception as exc:
        return _check(name, path, "PARSE_ERROR", "ERROR", str(exc))
    missing = sorted(required_columns - set(df.columns))
    if missing:
        return _check(name, path, "SCHEMA_ERROR", "ERROR", "missing columns: " + ",".join(missing))
    return _check(name, path, "OK", "INFO", f"columns={len(df.columns)}")


def _json_fields_check(name: str, path: Path, required_fields: set[str]) -> ConfigHealthCheck:
    data, error = _read_json(path)
    if error:
        return _check(name, path, "ERROR", "ERROR", error)
    missing = sorted(required_fields - set(data.keys()))
    if missing:
        return _check(name, path, "SCHEMA_ERROR", "ERROR", "missing fields: " + ",".join(missing))
    return _check(name, path, "OK", "INFO", "fields present")


def _json_status_check(
    name: str,
    path: Path,
    *,
    status_key: str,
    ok_values: set[str],
    warning_values: set[str] | None = None,
) -> ConfigHealthCheck:
    data, error = _read_json(path)
    if error:
        return _check(name, path, "ERROR", "ERROR", error)
    value = str(data.get(status_key, "UNKNOWN")).upper()
    if value in ok_values:
        return _check(name, path, value, "INFO", f"{status_key}={value}")
    if warning_values and value in warning_values:
        return _check(name, path, value, "WARNING", f"{status_key}={value}")
    return _check(name, path, value, "ERROR", f"{status_key}={value}")


def _risk_control_check(path: Path) -> ConfigHealthCheck:
    base = _file_check("risk_guard_control", path)
    if not base.passed:
        return base
    values = _read_env(path)
    required = {"trade_mode", "max_order_amount", "max_single_weight", "max_total_buy_weight"}
    missing = sorted(required - set(values.keys()))
    if missing:
        return _check("risk_guard_control", path, "SCHEMA_ERROR", "ERROR", "missing keys: " + ",".join(missing))
    mode = values.get("trade_mode", "").upper()
    severity = "INFO" if mode == "NORMAL" else "WARNING"
    status = "OK" if mode == "NORMAL" else mode or "UNKNOWN"
    return _check("risk_guard_control", path, status, severity, f"trade_mode={mode}")


def _execution_policy_check(path: Path) -> ConfigHealthCheck:
    data, error = _read_json(path)
    if error:
        return _check("execution_policy", path, "ERROR", "ERROR", error)
    modes = [str(value).upper() for value in data.get("allowed_modes", [])]
    adapters = [str(value) for value in data.get("allowed_adapters", [])]
    if not modes or not adapters:
        return _check("execution_policy", path, "SCHEMA_ERROR", "ERROR", "allowed_modes and allowed_adapters are required")
    if any(mode != "DRY_RUN" for mode in modes):
        missing = [
            key
            for key in ["approved_trade_date", "approved_strategy_id", "approval_id", "approved_by", "expires_at"]
            if not data.get(key)
        ]
        if missing:
            return _check("execution_policy", path, "SCHEMA_ERROR", "ERROR", "live policy missing: " + ",".join(missing))
    return _check("execution_policy", path, "OK", "INFO", f"modes={','.join(modes)}, adapters={','.join(adapters)}")


def _manual_validation_check(path: Path) -> ConfigHealthCheck:
    data, error = _read_json(path)
    if error:
        return _check("manual_fill_validation", path, "PENDING", "WARNING", error)
    status = str(data.get("status", "UNKNOWN")).upper()
    if bool(data.get("passed", False)) and status == "OK":
        return _check("manual_fill_validation", path, "OK", "INFO", "manual fills validated")
    return _check("manual_fill_validation", path, status, "WARNING", f"issues={len(data.get('issues', [])) if isinstance(data.get('issues'), list) else 0}")


def _broker_adapter_contract_check(path: Path) -> ConfigHealthCheck:
    data, error = _read_json(path)
    if error:
        return _check("broker_adapter_contract", path, "ERROR", "ERROR", error)
    status = str(data.get("status", "UNKNOWN")).upper()
    if status == "OK" and bool(data.get("passed", False)):
        return _check(
            "broker_adapter_contract",
            path,
            "OK",
            "INFO",
            f"adapter={data.get('adapter', '-')}, mode={data.get('mode', '-')}, submitted={bool(data.get('submitted', False))}",
        )
    return _check(
        "broker_adapter_contract",
        path,
        status,
        "ERROR",
        str(data.get("issue", "")) or f"status={status}",
    )


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "file not found"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, str(exc)
    if not isinstance(data, dict):
        return {}, "expected JSON object"
    return data, ""


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _check(name: str, path: Path, status: str, severity: str, detail: str) -> ConfigHealthCheck:
    return ConfigHealthCheck(
        name=name,
        status=status,
        severity=severity,
        path=str(path),
        detail=detail,
    )


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
