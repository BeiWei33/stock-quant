from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant.core.persistence.sqlite_store import SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect workflow run logs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    latest = subparsers.add_parser("latest", help="Show the latest workflow run.")
    latest.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    latest.add_argument("--workflow", default="daily")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "latest":
        store = SqliteStore(Path(args.sqlite))
        store.init_schema()
        run = store.load_latest_workflow_run(args.workflow)
        if run is None:
            print("{}")
            return
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
