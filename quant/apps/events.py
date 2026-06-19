from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from quant.core.persistence.sqlite_store import SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect local audit events.")
    parser.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    trace = subparsers.add_parser("trace", help="Show all events for a trace id.")
    trace.add_argument("--trace-id", required=True)
    trace.add_argument("--limit", type=int, default=100)
    trace.add_argument("--output-json", default="")
    trace.add_argument("--output-md", default="")
    trace.add_argument("--no-console", action="store_true")

    recent = subparsers.add_parser("recent", help="Show recent events.")
    recent.add_argument("--event-type", default="")
    recent.add_argument("--correlation-id", default="")
    recent.add_argument("--limit", type=int, default=50)
    recent.add_argument("--output-json", default="")
    recent.add_argument("--output-md", default="")
    recent.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    store = SqliteStore(Path(args.sqlite))
    store.init_schema()
    if args.command == "trace":
        events = store.load_trace(args.trace_id, limit=args.limit)
        title = f"Event Trace - {args.trace_id}"
    else:
        events = store.load_events(
            event_type=args.event_type or None,
            correlation_id=args.correlation_id or None,
            limit=args.limit,
        )
        title = "Recent Events"

    if args.output_json:
        _write_json(events, Path(args.output_json))
        print(f"Wrote events JSON to {args.output_json}")
    if args.output_md:
        Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_md).write_text(render_events_markdown(events, title), encoding="utf-8")
        print(f"Wrote events Markdown to {args.output_md}")
    if not args.no_console:
        print(render_events_markdown(events, title))


def render_events_markdown(events: pd.DataFrame, title: str) -> str:
    if events.empty:
        rows = "_No events found._"
    else:
        rows = _table(
            ["Time", "Type", "Trace", "Correlation", "Payload"],
            [
                [
                    _time_text(row.event_time),
                    row.event_type,
                    row.trace_id,
                    row.correlation_id,
                    _payload_summary(row.payload),
                ]
                for row in events.itertuples(index=False)
            ],
        )
    return "\n".join([f"# {title}", "", rows, ""])


def _write_json(events: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for record in events.to_dict(orient="records"):
        for key, value in list(record.items()):
            if hasattr(value, "isoformat"):
                record[key] = value.isoformat()
        records.append(record)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload_summary(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    keys = ["order_id", "fill_id", "ts_code", "side", "allowed", "total_asset", "status"]
    parts = [f"{key}={payload[key]}" for key in keys if key in payload]
    return "; ".join(parts) if parts else json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _time_text(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
