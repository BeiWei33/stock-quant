from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import yaml


@dataclass(frozen=True)
class ManualFillImportIssue:
    severity: str
    order_id: str
    field: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ManualFillImportReport:
    status: str
    passed: bool
    order_count: int
    imported_count: int
    matched_count: int
    unmatched_source_count: int
    total_fill_quantity: int
    total_fill_amount: float
    source_path: str
    output_path: str
    issues: list[ManualFillImportIssue]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passed": self.passed,
            "order_count": self.order_count,
            "imported_count": self.imported_count,
            "matched_count": self.matched_count,
            "unmatched_source_count": self.unmatched_source_count,
            "total_fill_quantity": self.total_fill_quantity,
            "total_fill_amount": self.total_fill_amount,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def import_manual_fills(
    *,
    order_ticket_path: Path,
    broker_fills_path: Path,
    output_path: Path,
    column_mapping: dict[str, list[str]] | None = None,
) -> ManualFillImportReport:
    orders = _read_csv(order_ticket_path)
    fills = _normalize_source(_read_csv(broker_fills_path), column_mapping=column_mapping)
    issues: list[ManualFillImportIssue] = []
    missing_order_columns = _required_columns(orders, _order_columns())
    if missing_order_columns:
        issues.extend(
            ManualFillImportIssue("ERROR", "", "order_ticket", f"missing column {column}")
            for column in missing_order_columns
        )
        return _write_report(order_ticket_path, broker_fills_path, output_path, orders, fills, issues)

    orders = _normalize_orders(orders)
    fill_rows = []
    matched_source_indexes: set[int] = set()
    for _, order in orders.iterrows():
        matches = _matching_source_rows(order, fills)
        matched_source_indexes.update(int(index) for index in matches.index)
        row, row_issues = _fill_template_row(order, matches)
        fill_rows.append(row)
        issues.extend(row_issues)

    unmatched = fills[~fills.index.isin(matched_source_indexes)]
    for _, row in unmatched.iterrows():
        issues.append(
            ManualFillImportIssue(
                "WARNING",
                str(row.get("order_id", "")),
                "source",
                f"unmatched source fill broker_order_id={row.get('broker_order_id', '')}",
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(fill_rows, columns=_fill_template_columns()).to_csv(output_path, index=False)
    return _write_report(order_ticket_path, broker_fills_path, output_path, orders, fills, issues, matched_source_indexes)


def load_fill_column_mapping(path: Path | None) -> dict[str, list[str]]:
    if path is None or not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_columns = payload.get("columns", payload)
    if not isinstance(raw_columns, dict):
        raise ValueError("fill import mapping must be a mapping or contain a columns mapping")
    result: dict[str, list[str]] = {}
    for target, raw_aliases in raw_columns.items():
        if raw_aliases is None:
            result[str(target)] = []
        elif isinstance(raw_aliases, str):
            result[str(target)] = [raw_aliases]
        elif isinstance(raw_aliases, list):
            result[str(target)] = [str(alias) for alias in raw_aliases]
        else:
            raise ValueError(f"fill import mapping for {target} must be a string or list")
    return result


def write_manual_fill_import_json(report: ManualFillImportReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_manual_fill_import_markdown(report: ManualFillImportReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_manual_fill_import_markdown(report), encoding="utf-8")
    return path


def render_manual_fill_import_markdown(report: ManualFillImportReport) -> str:
    summary_rows = [
        ["Status", report.status],
        ["Passed", report.passed],
        ["Orders", report.order_count],
        ["Imported Rows", report.imported_count],
        ["Matched Source Rows", report.matched_count],
        ["Unmatched Source Rows", report.unmatched_source_count],
        ["Total Fill Quantity", report.total_fill_quantity],
        ["Total Fill Amount", f"{report.total_fill_amount:,.2f}"],
        ["Source", report.source_path],
        ["Output", report.output_path],
    ]
    issue_rows = [
        [issue.severity, issue.order_id or "-", issue.field, issue.message]
        for issue in report.issues
    ]
    return "\n".join(
        [
            "# Manual Fill Import",
            "",
            _table(["Metric", "Value"], summary_rows),
            "",
            "## Issues",
            _table(["Severity", "Order", "Field", "Message"], issue_rows) if issue_rows else "_No issues._",
            "",
        ]
    )


def _fill_template_row(order: pd.Series, matches: pd.DataFrame) -> tuple[dict[str, object], list[ManualFillImportIssue]]:
    issues: list[ManualFillImportIssue] = []
    order_id = str(order["order_id"])
    planned_quantity = int(order["quantity"])
    if matches.empty:
        issues.append(ManualFillImportIssue("WARNING", order_id, "source", "no source fill matched this order"))
        return _blank_row(order), issues

    executable = matches[matches["status"].isin(["FILLED", "PARTIAL_FILLED", ""])]
    total_quantity = int(executable["quantity"].sum())
    total_amount = float(executable["amount"].sum())
    if total_quantity > planned_quantity:
        issues.append(
            ManualFillImportIssue(
                "ERROR",
                order_id,
                "quantity",
                f"imported quantity {total_quantity} exceeds planned quantity {planned_quantity}",
            )
        )
    status = _row_status(matches, total_quantity, planned_quantity)
    price = total_amount / total_quantity if total_quantity > 0 else 0.0
    return {
        "trade_date": str(order["trade_date"]),
        "ts_code": str(order["ts_code"]),
        "side": str(order["side"]).upper(),
        "quantity": str(total_quantity) if status in {"FILLED", "PARTIAL_FILLED"} else "0",
        "price": f"{price:.4f}" if total_quantity > 0 else "0.0000",
        "amount": f"{total_amount:.2f}" if total_amount > 0 else "0.00",
        "broker_order_id": str(order["broker_order_id"]),
        "order_id": order_id,
        "status": status,
        "operator_note": _note(matches),
    }, issues


def _row_status(matches: pd.DataFrame, total_quantity: int, planned_quantity: int) -> str:
    statuses = {str(value).upper() for value in matches["status"].tolist() if str(value).strip()}
    if total_quantity >= planned_quantity and planned_quantity > 0:
        return "FILLED"
    if total_quantity > 0:
        return "PARTIAL_FILLED"
    for status in ["CANCELLED", "REJECTED", "FAILED"]:
        if status in statuses:
            return status
    return ""


def _note(matches: pd.DataFrame) -> str:
    notes = sorted({str(value) for value in matches["operator_note"].tolist() if str(value).strip()})
    return "; ".join(notes)


def _blank_row(order: pd.Series) -> dict[str, object]:
    return {
        "trade_date": str(order["trade_date"]),
        "ts_code": str(order["ts_code"]),
        "side": str(order["side"]).upper(),
        "quantity": "",
        "price": "",
        "amount": "",
        "broker_order_id": str(order["broker_order_id"]),
        "order_id": str(order["order_id"]),
        "status": "",
        "operator_note": "",
    }


def _matching_source_rows(order: pd.Series, fills: pd.DataFrame) -> pd.DataFrame:
    order_id = str(order["order_id"])
    broker_order_id = str(order["broker_order_id"])
    matches = fills[fills["order_id"] == order_id]
    if matches.empty and broker_order_id:
        matches = fills[fills["broker_order_id"] == broker_order_id]
    return matches


def _write_report(
    order_ticket_path: Path,
    broker_fills_path: Path,
    output_path: Path,
    orders: pd.DataFrame,
    fills: pd.DataFrame,
    issues: list[ManualFillImportIssue],
    matched_source_indexes: set[int] | None = None,
) -> ManualFillImportReport:
    matched_source_indexes = matched_source_indexes or set()
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    imported_count = len(orders) if output_path.exists() else 0
    return ManualFillImportReport(
        status="OK" if not errors else "ERROR",
        passed=not errors,
        order_count=len(orders),
        imported_count=imported_count,
        matched_count=len(matched_source_indexes),
        unmatched_source_count=max(0, len(fills) - len(matched_source_indexes)),
        total_fill_quantity=int(fills["quantity"].sum()) if "quantity" in fills.columns and not fills.empty else 0,
        total_fill_amount=float(fills["amount"].sum()) if "amount" in fills.columns and not fills.empty else 0.0,
        source_path=str(broker_fills_path),
        output_path=str(output_path),
        issues=issues,
    )


def _normalize_source(
    df: pd.DataFrame,
    *,
    column_mapping: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    column_map = _source_column_map(column_mapping)
    normalized = pd.DataFrame()
    for target, aliases in column_map.items():
        source = next((alias for alias in aliases if alias in df.columns), None)
        normalized[target] = df[source] if source else ""
    for column in ["trade_date", "ts_code", "side", "broker_order_id", "order_id", "status", "operator_note"]:
        normalized[column] = normalized[column].fillna("").astype(str)
    normalized["side"] = normalized["side"].str.upper()
    normalized["status"] = normalized["status"].str.upper()
    normalized["quantity"] = pd.to_numeric(normalized["quantity"], errors="coerce").fillna(0).astype(int)
    normalized["price"] = pd.to_numeric(normalized["price"], errors="coerce").fillna(0.0).astype(float)
    normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce").fillna(
        normalized["quantity"] * normalized["price"]
    ).astype(float)
    normalized.loc[normalized["amount"] == 0, "amount"] = normalized["quantity"] * normalized["price"]
    return normalized


def _source_column_map(column_mapping: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    defaults = {
        "trade_date": ["trade_date", "date", "fill_date"],
        "ts_code": ["ts_code", "symbol", "code"],
        "side": ["side", "direction"],
        "quantity": ["quantity", "fill_quantity", "filled_quantity", "fill_qty"],
        "price": ["price", "fill_price", "avg_price"],
        "amount": ["amount", "fill_amount"],
        "broker_order_id": ["broker_order_id", "broker_order_no", "entrust_no"],
        "order_id": ["order_id", "client_order_id"],
        "status": ["status", "fill_status", "order_status"],
        "operator_note": ["operator_note", "note", "remark"],
    }
    if not column_mapping:
        return defaults
    merged = {key: list(value) for key, value in defaults.items()}
    for target, aliases in column_mapping.items():
        if target not in merged:
            continue
        custom = [alias for alias in aliases if alias not in merged[target]]
        merged[target] = custom + merged[target]
    return merged


def _normalize_orders(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in ["trade_date", "ts_code", "side", "order_id", "broker_order_id"]:
        result[column] = result[column].fillna("").astype(str)
    result["side"] = result["side"].str.upper()
    result["quantity"] = pd.to_numeric(result["quantity"], errors="coerce").fillna(0).astype(int)
    return result


def _required_columns(df: pd.DataFrame, required: set[str]) -> list[str]:
    return sorted(required - set(df.columns))


def _order_columns() -> set[str]:
    return {"trade_date", "ts_code", "side", "quantity", "order_id", "broker_order_id"}


def _fill_template_columns() -> list[str]:
    return [
        "trade_date",
        "ts_code",
        "side",
        "quantity",
        "price",
        "amount",
        "broker_order_id",
        "order_id",
        "status",
        "operator_note",
    ]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"fill import CSV not found: {path}")
    return pd.read_csv(path, dtype=str).fillna("")


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
