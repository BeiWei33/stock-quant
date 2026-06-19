from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from quant.core.reconciliation.trades import TradeReconciliationReport, reconcile_trade_activity


@dataclass(frozen=True)
class ManualFillIssue:
    severity: str
    row: int
    field: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ManualFillValidationReport:
    status: str
    passed: bool
    order_count: int
    fill_count: int
    matched_fill_count: int
    total_fill_quantity: int
    total_fill_amount: float
    issues: list[ManualFillIssue]
    order_ticket_path: str
    fill_template_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed": self.passed,
            "order_count": self.order_count,
            "fill_count": self.fill_count,
            "matched_fill_count": self.matched_fill_count,
            "total_fill_quantity": self.total_fill_quantity,
            "total_fill_amount": self.total_fill_amount,
            "issues": [issue.to_dict() for issue in self.issues],
            "order_ticket_path": self.order_ticket_path,
            "fill_template_path": self.fill_template_path,
        }


@dataclass(frozen=True)
class ManualReconciliationBundle:
    validation: ManualFillValidationReport
    reconciliation: TradeReconciliationReport
    local_orders_path: str
    broker_orders_path: str
    broker_fills_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "validation": self.validation.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "local_orders_path": self.local_orders_path,
            "broker_orders_path": self.broker_orders_path,
            "broker_fills_path": self.broker_fills_path,
        }


def validate_manual_fills(
    *,
    order_ticket_path: Path,
    fill_template_path: Path,
    require_complete: bool = True,
    amount_tolerance: float = 0.01,
) -> ManualFillValidationReport:
    orders = _read_csv(order_ticket_path)
    fills = _read_csv(fill_template_path)
    issues: list[ManualFillIssue] = []
    issues.extend(_required_columns(orders, _order_columns(), "order_ticket"))
    issues.extend(_required_columns(fills, _fill_columns(), "fill_template"))
    if issues:
        return _validation_report(order_ticket_path, fill_template_path, orders, fills, issues)

    normalized_orders = _normalize_orders(orders)
    normalized_fills = _normalize_fills(fills)
    order_ids = set(normalized_orders["order_id"].astype(str))
    seen_fill_orders: set[str] = set()
    for index, row in normalized_fills.iterrows():
        row_number = index + 2
        order_id = str(row["order_id"])
        if order_id not in order_ids:
            issues.append(ManualFillIssue("ERROR", row_number, "order_id", f"unknown order_id={order_id}"))
            continue
        seen_fill_orders.add(order_id)
        _validate_fill_row(row, row_number, issues, require_complete, amount_tolerance)
        order = normalized_orders[normalized_orders["order_id"].astype(str) == order_id].iloc[0]
        if str(row["ts_code"]) != str(order["ts_code"]):
            issues.append(ManualFillIssue("ERROR", row_number, "ts_code", "fill ts_code does not match order ticket"))
        if str(row["side"]).upper() != str(order["side"]).upper():
            issues.append(ManualFillIssue("ERROR", row_number, "side", "fill side does not match order ticket"))
        if int(row["quantity"]) > int(order["quantity"]):
            issues.append(ManualFillIssue("ERROR", row_number, "quantity", "fill quantity exceeds planned quantity"))

    missing = sorted(order_ids - seen_fill_orders)
    for order_id in missing:
        issues.append(ManualFillIssue("ERROR" if require_complete else "WARNING", 0, "order_id", f"missing fill row for {order_id}"))
    return _validation_report(order_ticket_path, fill_template_path, normalized_orders, normalized_fills, issues)


def build_manual_reconciliation(
    *,
    order_ticket_path: Path,
    fill_template_path: Path,
    trade_date: date,
    account_id: str = "paper",
    output_dir: Path = Path("research_store/reports"),
    require_complete: bool = True,
    amount_tolerance: float = 0.01,
) -> ManualReconciliationBundle:
    validation = validate_manual_fills(
        order_ticket_path=order_ticket_path,
        fill_template_path=fill_template_path,
        require_complete=require_complete,
        amount_tolerance=amount_tolerance,
    )
    if not validation.passed:
        raise ValueError("manual fill validation failed")

    orders = _normalize_orders(_read_csv(order_ticket_path))
    fills = _normalize_fills(_read_csv(fill_template_path))
    local_orders = _local_orders(orders)
    broker_orders = _broker_orders(orders)
    broker_fills = _broker_fills(fills)
    local_fills = _expected_fills_from_orders(broker_orders)
    output_dir.mkdir(parents=True, exist_ok=True)
    local_orders_path = output_dir / "manual_local_orders.csv"
    broker_orders_path = output_dir / "manual_broker_orders.csv"
    broker_fills_path = output_dir / "manual_broker_fills.csv"
    local_orders.to_csv(local_orders_path, index=False)
    broker_orders.to_csv(broker_orders_path, index=False)
    broker_fills.to_csv(broker_fills_path, index=False)
    reconciliation = reconcile_trade_activity(
        account_id=account_id,
        trade_date=trade_date,
        local_orders=local_orders,
        broker_orders=broker_orders,
        local_fills=local_fills,
        broker_fills=broker_fills,
        amount_tolerance=amount_tolerance,
    )
    return ManualReconciliationBundle(
        validation=validation,
        reconciliation=reconciliation,
        local_orders_path=str(local_orders_path),
        broker_orders_path=str(broker_orders_path),
        broker_fills_path=str(broker_fills_path),
    )


def write_manual_validation_json(report: ManualFillValidationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_manual_validation_markdown(report: ManualFillValidationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_manual_validation_markdown(report), encoding="utf-8")
    return path


def write_manual_reconciliation_json(bundle: ManualReconciliationBundle, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_manual_reconciliation_markdown(bundle: ManualReconciliationBundle, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_manual_reconciliation_markdown(bundle), encoding="utf-8")
    return path


def render_manual_validation_markdown(report: ManualFillValidationReport) -> str:
    rows = [
        ["Status", report.status],
        ["Passed", report.passed],
        ["Orders", report.order_count],
        ["Fill Rows", report.fill_count],
        ["Matched Fill Rows", report.matched_fill_count],
        ["Total Fill Quantity", report.total_fill_quantity],
        ["Total Fill Amount", f"{report.total_fill_amount:,.2f}"],
    ]
    issue_rows = [[issue.severity, issue.row or "-", issue.field, issue.message] for issue in report.issues]
    return "\n".join(
        [
            "# Manual Fill Validation",
            "",
            _table(["Metric", "Value"], rows),
            "",
            "## Issues",
            _table(["Severity", "Row", "Field", "Message"], issue_rows) if issue_rows else "_No issues._",
            "",
            f"Order Ticket: `{report.order_ticket_path}`",
            f"Fill Template: `{report.fill_template_path}`",
            "",
        ]
    )


def render_manual_reconciliation_markdown(bundle: ManualReconciliationBundle) -> str:
    reconciliation = bundle.reconciliation
    summary_rows = [
        ["Validation", bundle.validation.status],
        ["Reconciliation", reconciliation.status],
        ["Local Orders", reconciliation.local_order_count],
        ["Broker Orders", reconciliation.broker_order_count],
        ["Local Fills", reconciliation.local_fill_count],
        ["Broker Fills", reconciliation.broker_fill_count],
        ["Local Orders CSV", bundle.local_orders_path],
        ["Broker Orders CSV", bundle.broker_orders_path],
        ["Broker Fills CSV", bundle.broker_fills_path],
    ]
    order_rows = reconciliation.order_differences.to_dict(orient="records")
    fill_rows = reconciliation.fill_differences.to_dict(orient="records")
    return "\n".join(
        [
            f"# Manual Execution Reconciliation - {reconciliation.trade_date.isoformat()}",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Order Differences",
            _records_table(order_rows) if order_rows else "_No order differences._",
            "",
            "## Fill Differences",
            _records_table(fill_rows) if fill_rows else "_No fill differences._",
            "",
        ]
    )


def _validate_fill_row(
    row: pd.Series,
    row_number: int,
    issues: list[ManualFillIssue],
    require_complete: bool,
    amount_tolerance: float,
) -> None:
    status = str(row["status"]).upper()
    if require_complete and not status:
        issues.append(ManualFillIssue("ERROR", row_number, "status", "status is required"))
    if status and status not in {"FILLED", "PARTIAL_FILLED", "CANCELLED", "REJECTED", "FAILED"}:
        issues.append(ManualFillIssue("ERROR", row_number, "status", f"unsupported status={status}"))
    quantity = int(row["quantity"])
    price = float(row["price"])
    amount = float(row["amount"])
    if status in {"FILLED", "PARTIAL_FILLED"}:
        if quantity <= 0:
            issues.append(ManualFillIssue("ERROR", row_number, "quantity", "filled quantity must be positive"))
        if price <= 0:
            issues.append(ManualFillIssue("ERROR", row_number, "price", "filled price must be positive"))
        if amount <= 0:
            issues.append(ManualFillIssue("ERROR", row_number, "amount", "filled amount must be positive"))
        expected = quantity * price
        if abs(expected - amount) > amount_tolerance:
            issues.append(ManualFillIssue("ERROR", row_number, "amount", f"amount {amount:.2f} != quantity*price {expected:.2f}"))
    if status in {"CANCELLED", "REJECTED", "FAILED"} and quantity != 0:
        issues.append(ManualFillIssue("WARNING", row_number, "quantity", f"{status} row has non-zero quantity"))


def _validation_report(
    order_ticket_path: Path,
    fill_template_path: Path,
    orders: pd.DataFrame,
    fills: pd.DataFrame,
    issues: list[ManualFillIssue],
) -> ManualFillValidationReport:
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    fill_quantity = int(fills["quantity"].sum()) if "quantity" in fills.columns and not fills.empty else 0
    fill_amount = float(fills["amount"].sum()) if "amount" in fills.columns and not fills.empty else 0.0
    matched = int(fills["order_id"].astype(str).isin(set(orders["order_id"].astype(str))).sum()) if "order_id" in fills.columns and "order_id" in orders.columns else 0
    return ManualFillValidationReport(
        status="OK" if not errors else "ERROR",
        passed=not errors,
        order_count=len(orders),
        fill_count=len(fills),
        matched_fill_count=matched,
        total_fill_quantity=fill_quantity,
        total_fill_amount=fill_amount,
        issues=issues,
        order_ticket_path=str(order_ticket_path),
        fill_template_path=str(fill_template_path),
    )


def _local_orders(orders: pd.DataFrame) -> pd.DataFrame:
    return orders[["ts_code", "side", "quantity", "limit_price"]].rename(columns={"limit_price": "price"})


def _broker_orders(orders: pd.DataFrame) -> pd.DataFrame:
    result = orders[["ts_code", "side", "submitted_quantity", "submitted_price"]].copy()
    result["quantity"] = result["submitted_quantity"]
    result["price"] = result["submitted_price"]
    return result[["ts_code", "side", "quantity", "price"]]


def _broker_fills(fills: pd.DataFrame) -> pd.DataFrame:
    executable = fills[fills["status"].isin(["FILLED", "PARTIAL_FILLED"])].copy()
    return executable[["ts_code", "side", "quantity", "price", "amount"]]


def _expected_fills_from_orders(orders: pd.DataFrame) -> pd.DataFrame:
    result = orders.copy()
    result["amount"] = result["quantity"] * result["price"]
    return result[["ts_code", "side", "quantity", "price", "amount"]]


def _normalize_orders(orders: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()
    for column in ["trade_date", "ts_code", "side", "order_id", "broker_order_id"]:
        df[column] = df[column].fillna("").astype(str)
    df["side"] = df["side"].str.upper()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["limit_price"] = pd.to_numeric(df["limit_price"], errors="coerce").fillna(0.0).astype(float)
    df["submitted_quantity"] = pd.to_numeric(df["submitted_quantity"], errors="coerce").fillna(df["quantity"]).astype(int)
    df["submitted_price"] = pd.to_numeric(df["submitted_price"], errors="coerce").fillna(df["limit_price"]).astype(float)
    return df


def _normalize_fills(fills: pd.DataFrame) -> pd.DataFrame:
    df = fills.copy()
    for column in ["trade_date", "ts_code", "side", "order_id", "broker_order_id", "status"]:
        df[column] = df[column].fillna("").astype(str)
    df["side"] = df["side"].str.upper()
    df["status"] = df["status"].str.upper()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0).astype(float)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).astype(float)
    return df


def _required_columns(df: pd.DataFrame, required: set[str], label: str) -> list[ManualFillIssue]:
    missing = sorted(required - set(df.columns))
    return [ManualFillIssue("ERROR", 0, label, f"missing column {column}") for column in missing]


def _order_columns() -> set[str]:
    return {"trade_date", "ts_code", "side", "quantity", "limit_price", "order_id", "broker_order_id", "submitted_quantity", "submitted_price"}


def _fill_columns() -> set[str]:
    return {"trade_date", "ts_code", "side", "quantity", "price", "amount", "order_id", "broker_order_id", "status"}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"manual execution CSV not found: {path}")
    return pd.read_csv(path, dtype=str).fillna("")


def _records_table(records: list[dict[str, object]]) -> str:
    headers = list(records[0].keys())
    return _table(headers, [[record.get(header, "") for header in headers] for record in records])


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
