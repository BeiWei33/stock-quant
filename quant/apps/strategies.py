from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant.core.models import StrategyRegistration
from quant.core.persistence.sqlite_store import SqliteStore
from quant.core.strategy.factory import build_strategy
from quant.core.strategy.registry import build_strategy_registration


STRATEGY_CHOICES = ["momentum_rank", "quality_rank", "momentum_rank_trend", "quality_rank_trend"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and fingerprint strategy registrations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fingerprint = subparsers.add_parser("fingerprint", help="Build a strategy registration from local code.")
    fingerprint.add_argument("--strategy", default="momentum_rank", choices=STRATEGY_CHOICES)
    fingerprint.add_argument("--research-report", default="")
    fingerprint.add_argument("--status", default="research", choices=["research", "candidate", "paper", "production", "deprecated"])
    fingerprint.add_argument("--description", default="")
    fingerprint.add_argument("--output-json", default="")
    fingerprint.add_argument("--output-md", default="")
    fingerprint.add_argument("--no-console", action="store_true")

    list_cmd = subparsers.add_parser("list", help="List registered strategies from the local audit store.")
    list_cmd.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    list_cmd.add_argument("--status", default="")
    list_cmd.add_argument("--output-json", default="")
    list_cmd.add_argument("--output-md", default="")
    list_cmd.add_argument("--no-console", action="store_true")

    show = subparsers.add_parser("show", help="Show one registered strategy version.")
    show.add_argument("--sqlite", default="research_store/paper_trading.sqlite3")
    show.add_argument("--strategy-id", required=True)
    show.add_argument("--strategy-version", default="v1")
    show.add_argument("--output-json", default="")
    show.add_argument("--output-md", default="")
    show.add_argument("--no-console", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "fingerprint":
        registration = _fingerprint(args)
        _emit_one(registration, args.output_json, args.output_md, not args.no_console)
        return
    if args.command == "list":
        store = SqliteStore(Path(args.sqlite))
        store.init_schema()
        registrations = store.list_strategies(status=args.status or None)
        _emit_many(registrations, args.output_json, args.output_md, not args.no_console)
        return
    if args.command == "show":
        store = SqliteStore(Path(args.sqlite))
        store.init_schema()
        registration = store.load_strategy(args.strategy_id, args.strategy_version)
        if registration is None:
            raise SystemExit(f"strategy not found: {args.strategy_id}@{args.strategy_version}")
        _emit_one(registration, args.output_json, args.output_md, not args.no_console)


def render_strategy_markdown(registration: StrategyRegistration) -> str:
    rows = [
        ["Strategy", registration.strategy_id],
        ["Version", registration.strategy_version],
        ["Status", registration.status],
        ["Factor Set", registration.factor_set_id],
        ["Code Hash", _short_hash(registration.code_hash)],
        ["Config Hash", _short_hash(registration.config_hash)],
        ["Research Report", registration.research_report_path],
    ]
    manifest = _manifest_summary(registration.config_json)
    if manifest:
        rows.append(["Required Factors", ", ".join(manifest.get("required_factors", []))])
        rows.append(["Class", manifest.get("class_path", "")])
    return "\n".join(["# Strategy Registration", "", _table(["Field", "Value"], rows), ""])


def render_strategy_list_markdown(registrations: list[StrategyRegistration]) -> str:
    if not registrations:
        body = "_No strategies found._"
    else:
        body = _table(
            ["Strategy", "Version", "Status", "Factor Set", "Config Hash", "Research Report"],
            [
                [
                    registration.strategy_id,
                    registration.strategy_version,
                    registration.status,
                    registration.factor_set_id,
                    _short_hash(registration.config_hash),
                    registration.research_report_path,
                ]
                for registration in registrations
            ],
        )
    return "\n".join(["# Strategy Registry", "", body, ""])


def _fingerprint(args) -> StrategyRegistration:
    strategy = build_strategy(args.strategy)
    factor_set_id = "+".join(factor.name for factor in strategy.required_factors()) or "none"
    return build_strategy_registration(
        strategy,
        description=args.description or f"{strategy.strategy_id} strategy",
        factor_set_id=factor_set_id,
        research_report_path=args.research_report,
        status=args.status,
    )


def _emit_one(
    registration: StrategyRegistration,
    output_json: str,
    output_md: str,
    print_console: bool,
) -> None:
    if output_json:
        _write_json(registration.to_dict(), Path(output_json))
        print(f"Wrote strategy JSON to {output_json}")
    if output_md:
        _write_text(render_strategy_markdown(registration), Path(output_md))
        print(f"Wrote strategy Markdown to {output_md}")
    if print_console:
        print(render_strategy_markdown(registration))


def _emit_many(
    registrations: list[StrategyRegistration],
    output_json: str,
    output_md: str,
    print_console: bool,
) -> None:
    if output_json:
        _write_json([registration.to_dict() for registration in registrations], Path(output_json))
        print(f"Wrote strategy registry JSON to {output_json}")
    if output_md:
        _write_text(render_strategy_list_markdown(registrations), Path(output_md))
        print(f"Wrote strategy registry Markdown to {output_md}")
    if print_console:
        print(render_strategy_list_markdown(registrations))


def _manifest_summary(config_json: str) -> dict[str, object]:
    if not config_json:
        return {}
    try:
        value = json.loads(config_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _short_hash(value: str) -> str:
    return value[:12] if value else ""


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
