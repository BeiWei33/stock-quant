from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.reconciliation.positions import reconcile_positions
from quant.core.reconciliation.trades import TradeReconciliationReport, reconcile_trade_activity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile local and broker account records.")
    parser.add_argument("--local-positions")
    parser.add_argument("--broker-positions")
    parser.add_argument("--local-orders")
    parser.add_argument("--broker-orders")
    parser.add_argument("--local-fills")
    parser.add_argument("--broker-fills")
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--account-id", default="paper")
    parser.add_argument("--output", default="research_store/reports/reconciliation.json")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    parser.add_argument("--amount-tolerance", type=float, default=0.01)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    trade_date = pd.to_datetime(args.trade_date).date()
    store = SqliteStore(Path(args.sqlite))
    store.init_schema()
    if _has_trade_activity_args(args):
        report = reconcile_trade_activity(
            account_id=args.account_id,
            trade_date=trade_date,
            local_orders=_read_optional_csv(args.local_orders),
            broker_orders=_read_optional_csv(args.broker_orders),
            local_fills=_read_optional_csv(args.local_fills),
            broker_fills=_read_optional_csv(args.broker_fills),
            amount_tolerance=args.amount_tolerance,
        )
        store.save_trade_reconciliation_report(report)
        payload = report.to_dict()
        markdown = render_trade_reconciliation_markdown(report)
    else:
        if not args.local_positions or not args.broker_positions:
            raise ValueError("positions reconciliation requires --local-positions and --broker-positions")
        report = reconcile_positions(
            account_id=args.account_id,
            trade_date=trade_date,
            local_positions=pd.read_csv(args.local_positions),
            broker_positions=pd.read_csv(args.broker_positions),
        )
        store.save_reconciliation_report(report)
        payload = {
            "report_id": report.report_id,
            "account_id": report.account_id,
            "trade_date": report.trade_date.isoformat(),
            "status": report.status,
            "local_count": report.local_count,
            "broker_count": report.broker_count,
            "differences": report.differences.to_dict(orient="records"),
        }
        markdown = render_position_reconciliation_markdown(payload)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.output_md:
        markdown_path = Path(args.output_md)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote reconciliation Markdown to {markdown_path}")
    print(f"Wrote reconciliation report to {output}")
    print(f"Saved reconciliation audit trail to {args.sqlite}")


def render_trade_reconciliation_markdown(report: TradeReconciliationReport) -> str:
    summary_rows = [
        ["Report ID", report.report_id],
        ["Status", report.status],
        ["Local Orders", report.local_order_count],
        ["Broker Orders", report.broker_order_count],
        ["Local Fills", report.local_fill_count],
        ["Broker Fills", report.broker_fill_count],
    ]
    order_rows = report.order_differences.to_dict(orient="records")
    fill_rows = report.fill_differences.to_dict(orient="records")
    return "\n".join(
        [
            f"# Trade Reconciliation - {report.trade_date.isoformat()}",
            "",
            "## Summary",
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


def render_position_reconciliation_markdown(payload: dict[str, object]) -> str:
    differences = payload.get("differences", [])
    rows = [
        ["Report ID", payload["report_id"]],
        ["Status", payload["status"]],
        ["Local Positions", payload["local_count"]],
        ["Broker Positions", payload["broker_count"]],
    ]
    return "\n".join(
        [
            f"# Position Reconciliation - {payload['trade_date']}",
            "",
            "## Summary",
            _table(["Metric", "Value"], rows),
            "",
            "## Differences",
            _records_table(differences) if isinstance(differences, list) and differences else "_No differences._",
            "",
        ]
    )


def _has_trade_activity_args(args: argparse.Namespace) -> bool:
    return any([args.local_orders, args.broker_orders, args.local_fills, args.broker_fills])


def _read_optional_csv(path: str | None) -> pd.DataFrame | None:
    return pd.read_csv(path) if path else None


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


if __name__ == "__main__":
    main()
