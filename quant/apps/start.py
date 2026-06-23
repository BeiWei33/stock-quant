from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_dir: Path
    manifest_path: Path
    manifest_md_path: Path
    manifest_html_path: Path
    copied_count: int
    skipped_count: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the personal quant system through a simple, safe paper-trading entrypoint."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser(
        "demo",
        help="Run the safe sample-data paper flow and refresh execution reports.",
    )
    _add_common_flags(demo)

    daily = subparsers.add_parser(
        "daily",
        help="Run the Python-only sample-data daily workflow and daily report.",
    )
    _add_common_flags(daily)

    akshare = subparsers.add_parser(
        "akshare",
        help="Run the daily workflow with automatic A-share market data fallback.",
    )
    akshare.add_argument("--start-date", help="Start date, default is about 260 calendar days ago.")
    akshare.add_argument("--end-date", help="End date, default is today.")
    akshare.add_argument("--symbols", help="Comma-separated A-share symbols, e.g. 600519.SH,000001.SZ.")
    akshare.add_argument("--symbols-file", help="Text file with one A-share symbol per line.")
    akshare.add_argument("--limit", type=int, default=30, help="Limit A-share collection size.")
    _add_common_flags(akshare)

    akshare_backtest = subparsers.add_parser(
        "akshare-backtest",
        help="Collect full-market A-share data for a date range and run a backtest.",
    )
    akshare_backtest.add_argument("--start-date", required=True, help="Backtest start date.")
    akshare_backtest.add_argument("--end-date", required=True, help="Backtest end date.")
    akshare_backtest.add_argument(
        "--limit",
        type=int,
        help="Optional test limit. Omit it for the full A-share universe.",
    )
    akshare_backtest.add_argument("--rebalance", choices=["weekly", "monthly"], default="weekly")
    akshare_backtest.add_argument("--initial-cash", type=float, default=1_000_000)
    akshare_backtest.add_argument("--multi-strategy", help="Comma-separated strategy ids for portfolio backtest.")
    akshare_backtest.add_argument("--allocation-method", choices=["equal", "risk_parity"], default="risk_parity")
    akshare_backtest.add_argument("--target-volatility", type=float)
    akshare_backtest.add_argument("--max-strategy-weight", type=float, default=0.60)
    _add_common_flags(akshare_backtest)

    practice_fills = subparsers.add_parser(
        "practice-fills",
        help="Practice broker fill import with sample fills without overwriting real fills.",
    )
    _add_common_flags(practice_fills)

    import_fills = subparsers.add_parser(
        "import-fills",
        help="Import a real broker fill CSV into the manual fill template and refresh execution reports.",
    )
    import_fills.add_argument("--source", required=True, help="Broker/exported fill CSV path.")
    import_fills.add_argument("--mapping-config", default="config/fill_import.yaml")
    import_fills.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Only import and validate fills; do not refresh execution reports.",
    )
    _add_common_flags(import_fills)

    subparsers.add_parser("status", help="Print the latest local system status.")
    doctor = subparsers.add_parser("doctor", help="Explain latest reports, blockers, warnings, and useful files.")
    doctor.add_argument("--output-md", default="research_store/reports/operator_doctor.md")
    subparsers.add_parser("paths", help="List the most useful local files to open next.")
    home = subparsers.add_parser("home", help="Generate a single operator home HTML page.")
    home.add_argument("--output-html", default="research_store/reports/operator_home.html")
    snapshot = subparsers.add_parser("snapshot", help="Archive the latest key reports with a manifest.")
    snapshot.add_argument("--output-dir", default="research_store/archive")
    snapshot.add_argument("--label", default="")
    snapshot.add_argument("--dry-run", action="store_true", help="Show what would be archived.")
    return parser


def main(argv: list[str] | None = None) -> None:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args:
        raw_args = ["demo"]
    elif raw_args[0].startswith("-"):
        raw_args = ["demo", *raw_args]
    args = build_parser().parse_args(raw_args)

    if args.command == "status":
        print(render_status())
        return
    if args.command == "doctor":
        text = render_doctor()
        path = write_operator_doctor_markdown(Path(args.output_md), text)
        print(text)
        print()
        print(f"宸插啓鍏ヤ綋妫€鎶ュ憡: {path}")
        return
    if args.command == "paths":
        print(render_paths())
        return
    if args.command == "home":
        path = write_operator_home_html(Path(args.output_html))
        print(f"宸茬敓鎴愭搷浣滈椤? {path}")
        return
    if args.command == "snapshot":
        result = create_operator_snapshot(
            output_dir=Path(args.output_dir),
            label=args.label,
            dry_run=bool(args.dry_run),
        )
        verb = "\u5c06\u5f52\u6863" if args.dry_run else "\u5df2\u5f52\u6863"
        print(
            f"{verb} {result.copied_count} \u4e2a\u6587\u4ef6\u5230 {result.snapshot_dir} "
            f"({result.skipped_count} \u4e2a\u6587\u4ef6\u4e0d\u5b58\u5728)\u3002",
        )
        print(f"\u6e05\u5355 JSON: {result.manifest_path}")
        print(f"\u6e05\u5355 Markdown: {result.manifest_md_path}")
        print(f"\u6e05\u5355 HTML: {result.manifest_html_path}")
        return

    if args.command == "daily":
        steps = build_daily_steps()
    elif args.command == "akshare":
        steps = build_akshare_steps(
            start_date=args.start_date,
            end_date=args.end_date,
            symbols=args.symbols,
            symbols_file=args.symbols_file,
            limit=args.limit,
        )
    elif args.command == "akshare-backtest":
        steps = build_akshare_backtest_steps(
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            rebalance=args.rebalance,
            initial_cash=args.initial_cash,
            multi_strategy=args.multi_strategy,
            allocation_method=args.allocation_method,
            target_volatility=args.target_volatility,
            max_strategy_weight=args.max_strategy_weight,
        )
    elif args.command == "demo":
        steps = build_demo_steps()
    elif args.command == "practice-fills":
        missing = missing_practice_fill_inputs()
        if missing and not args.dry_run:
            print("Cannot practice fill import yet. Missing:")
            for path in missing:
                print(f"  - {path}")
            print()
            print("Run this first:")
            print("  python -m quant.apps.start")
            raise SystemExit(2)
        steps = build_practice_fill_steps()
    elif args.command == "import-fills":
        missing = missing_real_fill_inputs(Path(args.source))
        if missing and not args.dry_run:
            print("Cannot import real fills yet. Missing:")
            for path in missing:
                print(f"  - {path}")
            print()
            print("Run this first if the order ticket is missing:")
            print("  python -m quant.apps.start")
            raise SystemExit(2)
        steps = build_real_fill_import_steps(
            Path(args.source),
            mapping_config=Path(args.mapping_config) if args.mapping_config else None,
            refresh=not args.skip_refresh,
        )
    else:
        raise SystemExit("unknown command")

    run_steps(steps, dry_run=bool(args.dry_run), keep_going=bool(args.keep_going))
    if not args.dry_run:
        home_path = write_operator_home_html()
        if args.command == "daily":
            print()
            print("Daily paper workflow completed.")
            print("Next files to open:")
            print(f"  - {home_path}")
            print("  - research_store/reports/daily_report.html")
            print("  - research_store/reports/daily_summary.json")
            print("  - research_store/reports/paper_plan.json")
            print()
            print("Run the full safe execution demo with:")
            print("  python -m quant.apps.start")
            return
        if args.command == "akshare":
            print()
            print("Auto A-share daily workflow completed.")
            print("Next files to open:")
            print(f"  - {home_path}")
            print("  - research_store/reports/daily_report.html")
            print("  - research_store/reports/daily_summary.json")
            print()
            print("Reminder: this is still paper trading. QMT live trading is not connected.")
            return
        if args.command == "akshare-backtest":
            print()
            print("Auto A-share full-market backtest completed.")
            print("Backtest files:")
            print("  - research_store/reports/akshare_backtest.md")
            print("  - research_store/reports/akshare_backtest.json")
            print("  - research_store/backtest_runs/market_data_*.sqlite3")
            return
        if args.command == "practice-fills":
            print()
            print("Sample fill import completed.")
            print("This did not overwrite the real manual fill template.")
            print("Practice files:")
            print(f"  - {home_path}")
            print("  - research_store/sample/manual_fill_template.imported.csv")
            print("  - research_store/reports/manual_fill_import_sample.md")
            print("  - research_store/reports/manual_fill_validation_sample.md")
            print("  - research_store/reports/manual_fill_import_sample_audit.jsonl")
            return
        if args.command == "import-fills":
            print()
            print("Real fill import completed.")
            print("Updated files:")
            print(f"  - {home_path}")
            print("  - research_store/reports/manual_fill_template.csv")
            print("  - research_store/reports/manual_fill_import.md")
            print("  - research_store/reports/manual_fill_validation.md")
            if not args.skip_refresh:
                print("  - research_store/reports/execution_dashboard.html")
            return
        print()
        print(render_status())
        print()
        print("Next files to open:")
        print(f"  - {home_path}")
        print("  - research_store/reports/daily_report.html")
        print("  - research_store/reports/execution_dashboard.html")
        print("  - research_store/monitoring/readiness.md")


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without running them.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue after a failed step and report failures at the end.",
    )


def build_daily_steps() -> list[Step]:
    py = sys.executable
    return [
        Step("Generate sample data", (py, "scripts/generate_sample_data.py")),
        Step(
            "Clean sample bars",
            (
                py,
                "-m",
                "quant.apps.clean",
                "daily-bars",
                "--input",
                "research_store/sample/daily_bar.csv",
                "--output",
                "research_store/sample/daily_bar.cleaned.csv",
                "--config",
                "config/cleaning.yaml",
                "--report",
                "research_store/reports/data_cleaning.json",
                "--report-md",
                "research_store/reports/data_cleaning.md",
            ),
        ),
        Step(
            "Run daily paper workflow",
            (
                py,
                "-m",
                "quant.apps.daily",
                "--config",
                "config/daily.yaml",
                "--no-lock",
            ),
        ),
        Step(
            "Render daily report",
            (
                py,
                "-m",
                "quant.apps.report",
                "daily",
                "--summary",
                "research_store/reports/daily_summary.json",
                "--paper-sqlite",
                "research_store/paper_trading.sqlite3",
                "--output-md",
                "research_store/reports/daily_report.md",
                "--output-html",
                "research_store/reports/daily_report.html",
            ),
        ),
]


def build_akshare_steps(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: str | None = None,
    symbols_file: str | None = None,
    limit: int = 30,
) -> list[Step]:
    """Build steps for the automatic A-share daily workflow."""
    py = sys.executable
    steps = [
        Step(
            "Run auto A-share daily paper workflow",
            _collect_cmd(py, start_date, end_date, symbols, symbols_file, limit),
        ),
        Step(
            "Render daily report",
            (
                py,
                "-m",
                "quant.apps.report",
                "daily",
                "--summary",
                "research_store/reports/daily_summary.json",
                "--paper-sqlite",
                "research_store/paper_trading.sqlite3",
                "--output-md",
                "research_store/reports/daily_report.md",
                "--output-html",
                "research_store/reports/daily_report.html",
            ),
        ),
    ]
    return steps


def _collect_cmd(
    py: str,
    start_date: str | None,
    end_date: str | None,
    symbols: str | None,
    symbols_file: str | None,
    limit: int = 30,
) -> tuple[str, ...]:
    """Build the auto market-data collect command."""
    cmd: list[str] = [
        py,
        "-m",
        "quant.apps.daily",
        "--source",
        "auto",
        "--no-lock",
    ]
    if start_date:
        cmd.extend(["--start-date", start_date])
    else:
        d = (datetime.now(UTC).date() - timedelta(days=260)).isoformat()
        cmd.extend(["--start-date", d])
    if end_date:
        cmd.extend(["--end-date", end_date])
    else:
        d = (datetime.now(UTC).date()).isoformat()
        cmd.extend(["--end-date", d])
    if symbols:
        cmd.extend(["--akshare-symbols", symbols])
    if limit:
        cmd.extend(["--akshare-limit", str(limit)])
    if symbols_file:
        cmd.extend(["--akshare-symbols-file", symbols_file])
    return tuple(cmd)


def build_akshare_backtest_steps(
    *,
    start_date: str,
    end_date: str,
    limit: int | None = None,
    rebalance: str = "weekly",
    initial_cash: float = 1_000_000,
    multi_strategy: str | None = None,
    allocation_method: str = "risk_parity",
    target_volatility: float | None = None,
    max_strategy_weight: float = 0.60,
) -> list[Step]:
    """Build steps for automatic A-share full-market backtest."""
    py = sys.executable
    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    market_sqlite = f"research_store/backtest_runs/market_data_{run_stamp}.sqlite3"
    backtest_cmd: list[str] = [
        py,
        "-m",
        "quant.apps.backtest",
        "--sqlite",
        market_sqlite,
        "--start-date",
        start_date,
        "--end-date",
        end_date,
        "--rebalance",
        rebalance,
        "--initial-cash",
        str(initial_cash),
        "--output",
        "research_store/reports/akshare_backtest.json",
        "--output-md",
        "research_store/reports/akshare_backtest.md",
    ]
    if multi_strategy:
        backtest_cmd.extend(["--multi-strategy", multi_strategy])
        backtest_cmd.extend(["--allocation-method", allocation_method])
        backtest_cmd.extend(["--max-strategy-weight", str(max_strategy_weight)])
        if target_volatility is not None:
            backtest_cmd.extend(["--target-volatility", str(target_volatility)])
    return [
        Step(
            "Collect full-market market data",
            (
                py,
                "-m",
                "quant.apps.collect",
                "--source",
                "auto",
                "--akshare-all",
                "--start-date",
                start_date,
                "--end-date",
                end_date,
                "--sqlite",
                market_sqlite,
                *(["--akshare-limit", str(limit)] if limit else []),
            ),
        ),
        Step(
            "Run backtest on collected data",
            tuple(backtest_cmd),
        ),
    ]


def build_demo_steps() -> list[Step]:
    """Build steps for the full safe demo flow."""
    py = sys.executable
    return [
        *build_daily_steps(),
        Step(
            "Refresh execution reports",
            (py, "-m", "quant.apps.broker", "refresh", "--no-console"),
        ),
    ]


def build_practice_fill_steps() -> list[Step]:
    """Build steps for practicing fill import with sample data."""
    py = sys.executable
    return [
        Step(
            "Practice fill import",
            (
                py, "-m", "quant.apps.fill", "import",
                "--source", "research_store/sample/broker_fills_sample.csv",
                "--output-template", "research_store/sample/broker_fills_sample.imported.csv",
                "--report", "research_store/reports/manual_fill_import_sample.json",
                "--report-md", "research_store/reports/manual_fill_import_sample.md",
                "--audit-log", "research_store/reports/manual_fill_import_sample_audit.jsonl",
                "--validate-only",
            ),
        ),
        Step(
            "Validate imported sample fills",
            (
                py, "-m", "quant.apps.fill", "validate",
                "--template", "research_store/sample/broker_fills_sample.imported.csv",
                "--output", "research_store/reports/manual_fill_validation_sample.json",
                "--output-md", "research_store/reports/manual_fill_validation_sample.md",
            ),
        ),
    ]


def build_real_fill_import_steps(
    source: Path,
    *,
    mapping_config: Path | None = None,
    refresh: bool = True,
) -> list[Step]:
    """Build steps for importing real broker fills."""
    py = sys.executable
    steps: list[Step] = [
        Step(
            "Import real broker fills",
            (
                py, "-m", "quant.apps.fill", "import",
                "--source", str(source),
                "--mapping-config", str(mapping_config or Path("config/fill_import.yaml")),
                "--output-template", "research_store/reports/manual_fill_template.csv",
                "--report", "research_store/reports/manual_fill_import.json",
                "--report-md", "research_store/reports/manual_fill_import.md",
                "--audit-log", "research_store/reports/execution_audit.jsonl",
            ),
        ),
    ]
    if refresh:
        steps.append(
            Step("Refresh execution dashboard",
                 (py, "-m", "quant.apps.broker", "refresh", "--no-console")),
        )
    return steps

def missing_practice_fill_inputs() -> list[Path]:
    root = ROOT
    paths = [
        root / "research_store" / "reports" / "manual_order_ticket.csv",
        root / "research_store" / "sample" / "broker_fills_sample.csv",
    ]
    return [p for p in paths if not p.exists()]


def missing_real_fill_inputs(source: Path) -> list[Path]:
    root = ROOT
    paths = [
        source,
        root / "research_store" / "reports" / "manual_order_ticket.csv",
    ]
    return [p for p in paths if not p.exists()]


def run_steps(
    steps: Iterable[Step],
    *,
    dry_run: bool = False,
    keep_going: bool = False,
) -> None:
    """Run a sequence of Step commands."""
    failures = []
    for step in steps:
        label = "DRY-RUN" if dry_run else "RUN"
        print(f"[{label}] {step.name}")
        if dry_run:
            print("  " + " ".join(step.command))
            if step.note:
                print(f"  note: {step.note}")
            continue
        print("  " + " ".join(step.command))
        result = subprocess.run(step.command, capture_output=False)
        if result.returncode != 0:
            msg = f"Step {step.name!r} failed with exit code {result.returncode}"
            print(f"  [FAIL] {msg}")
            failures.append((step.name, msg))
            if not keep_going:
                raise RuntimeError(msg)
    if failures:
        parts = [f"\n{len(failures)} step(s) failed:"]
        parts += [f"  - {n}: {e}" for n, e in failures]
        raise RuntimeError("\n".join(parts))


# ---- Status / Doctor / Paths ----


def latest_status_payload() -> dict[str, object]:
    summary_path = ROOT / "research_store" / "reports" / "daily_summary.json"
    if summary_path.exists():
        import json
        return json.loads(summary_path.read_text("utf-8"))
    return {
        "daily_run_status": "MISSING",
        "next_action": "\u5148\u8fd0\u884c `python -m quant.apps.start daily`\u3002",
    }


def render_status() -> str:
    p = latest_status_payload()
    status = p.get("run_status", "N/A")
    ds = p.get("data_source", "csv")
    return (
        "=" * 40 + "\n  Personal Quant System Status\n" + "=" * 40
        + f"\n\n  Status:       {status}"
        + f"\n  Data source:  {ds}"
        + "\n  Paper:        true\n  Live:         false"
    )


def write_operator_doctor_markdown(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def render_doctor() -> str:
    p = latest_status_payload()
    status = p.get("run_status", "N/A")
    warnings = []
    blocks = []
    reminders = []
    val_path = ROOT / "research_store" / "reports" / "manual_fill_validation.json"
    rec_path = ROOT / "research_store" / "reports" / "manual_reconciliation.json"
    qmt_config = ROOT / "config" / "qmt.yaml"
    if val_path.exists():
        import json
        try:
            val = json.loads(val_path.read_text("utf-8"))
            issues = val.get("issues", [])
            if issues:
                blocks.append("manual_fill_validation: ERROR (issues=" + str(len(issues)) + ") -> " + str(val_path))
        except Exception:
            pass
    if rec_path.exists():
        import json
        try:
            rec = json.loads(rec_path.read_text("utf-8"))
            if rec.get("status") == "SKIPPED" or not rec.get("ok"):
                reminders.append("manual_reconciliation: SKIPPED -> " + str(rec_path))
        except Exception:
            pass
    if not qmt_config.exists():
        warnings.append("qmt_interface: qmt interface not configured")
    exec_status = "BLOCKED" if blocks else "READY"
    config_health = "WARNING" if warnings else "OK"
    u_doctor = "\u4f53\u68c0"
    u_summary = "\u6458\u8981"
    u_daily = "\u65e5\u6d41\u7a0b"
    u_paper = "\u7eb8\u9762\u53ef\u7528"
    u_live = "\u5b9e\u76d8\u53ef\u7528"
    u_exec = "\u6267\u884c\u72b6\u6001"
    u_config = "\u914d\u7f6e\u5065\u5eb7"
    u_meaning = "\u542b\u4e49"
    u_action = "\u586b\u5199\u6216\u5bfc\u5165\u771f\u5b9e\u6210\u4ea4\uff0c\u7136\u540e\u8fd0\u884c"
    u_blocks = "\u6267\u884c\u963b\u585e"
    u_reminders = "\u6267\u884c\u63d0\u9192"
    u_warnings_title = "\u5c31\u7eea\u963b\u585e"
    lines = [
        "# Personal Quant System " + u_doctor,
        "",
        "## " + u_summary,
        "  - " + u_daily + ": " + status,
        "  - " + u_paper + ": true",
        "  - " + u_live + ": false",
        "  - " + u_exec + ": " + exec_status,
        "  - " + u_config + ": " + config_health,
        "",
        "## " + u_meaning,
        "  " + u_action + " `python -m quant.apps.broker refresh --no-console`\u3002",
    ]
    if blocks:
        lines.extend(["", "## " + u_blocks] + ["  - " + b for b in blocks])
    if reminders:
        lines.extend(["", "## " + u_reminders] + ["  - " + r for r in reminders])
    if warnings:
        lines.extend(["", "## " + u_warnings_title] + ["  - " + w for w in warnings])
    return "\n".join(lines)
def render_paths() -> str:
    candidates = [
        ("Operator Home", ROOT / "research_store" / "reports" / "operator_home.html"),
        ("Daily Report", ROOT / "research_store" / "reports" / "daily_report.html"),
        ("Execution Dashboard", ROOT / "research_store" / "reports" / "execution_dashboard.html"),
        ("Daily Summary JSON", ROOT / "research_store" / "reports" / "daily_summary.json"),
        ("Paper Plan", ROOT / "research_store" / "reports" / "paper_plan.json"),
        ("Data Quality", ROOT / "research_store" / "reports" / "data_quality.md"),
        ("Risk Guard", ROOT / "research_store" / "reports" / "risk_guard.md"),
        ("Manual Fill Template", ROOT / "research_store" / "reports" / "manual_fill_template.csv"),
    ]
    lines = ["# Useful Files", ""]
    for label, path in candidates:
        mark = "+" if path.exists() else "-"
        lines.append(f"  [{mark}] {label}  -> {path}")
    return "\n".join(lines)


# ---- Home page ----


def write_operator_home_html(output_html=None):
    output = Path(output_html) if output_html else ROOT / "research_store" / "reports" / "operator_home.html"
    html = render_operator_home_html()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def render_operator_home_html() -> str:
    p = latest_status_payload()
    status = p.get("run_status", "N/A")
    exec_blocked = not (ROOT / "research_store" / "reports" / "manual_fill_validation.json").exists()
    latest_snap = None
    archive_dir = ROOT / "research_store" / "archive"
    if archive_dir.exists():
        dirs = sorted([d for d in archive_dir.iterdir() if d.is_dir()], reverse=True)
        if dirs:
            rel = dirs[0].resolve().relative_to((ROOT / "research_store").resolve())
            latest_snap = str(rel.as_posix())
    warnings = []
    val_path = ROOT / "research_store" / "reports" / "manual_fill_validation.json"
    rec_path = ROOT / "research_store" / "reports" / "manual_reconciliation.json"
    if val_path.exists():
        import json
        try:
            val = json.loads(val_path.read_text("utf-8"))
            issues = val.get("issues", [])
            if issues:
                warnings.append(f"<li><strong>manual_fill_validation</strong>: ERROR - issues={len(issues)}</li>")
            if rec_path.exists():
                rec = json.loads(rec_path.read_text("utf-8"))
                if rec.get("status") == "SKIPPED" or not rec.get("ok"):
                    warnings.append("<li><strong>manual_reconciliation</strong>: SKIPPED</li>")
        except Exception:
            pass
    if not (ROOT / "config" / "qmt.yaml").exists():
        warnings.append("<li><strong>qmt_interface</strong>: qmt interface not configured</li>")
    warnings_html = "\n".join(warnings) if warnings else "<p class=\"empty\">None</p>"
    snap_links_html = ""
    if latest_snap:
        snap_url = latest_snap + "/snapshot_manifest.md"
        snap_links_html = f"<div class=\"links\"><a href=\"{snap_url}\">{latest_snap.split("/")[-1]}</a></div>"
    else:
        snap_links_html = "<div class=\"links\"><p class=\"empty\">None</p></div>"
    exec_label = "BLOCKED" if exec_blocked else "READY"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>\u4e2a\u4eba\u91cf\u5316\u7cfb\u7edf\u64cd\u4f5c\u9996\u9875</title>
<style>:root{{color-scheme:light;--ink:#172033;--muted:#667085;--line:#d7deea;--bg:#f5f7fb;--panel:#fff;--accent:#0f766e;}}
*{{box-sizing:border-box;}}
body{{margin:0;font-family:Arial,sans-serif;color:var(--ink);background:var(--bg);}}
.shell{{width:min(1100px,calc(100%-32px));margin:28px auto 48px;}}
.hero{{padding:24px 0 18px;border-bottom:1px solid var(--line);}}
h1{{margin:0;font-size:42px;line-height:1;}}
h2{{margin:0 0 14px;font-size:20px;}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0;}}
.metric,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px;}}
.metric span{{display:block;color:var(--muted);font-size:13px;margin-bottom:8px;}}
.metric strong{{display:block;font-size:22px;overflow-wrap:anywhere;}}
.panel{{margin-top:14px;padding:16px;}}
.actions,.links{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}}
.command{{border:1px solid var(--line);border-radius:8px;padding:12px;background:#fbfcfe;}}
.command span{{display:block;color:var(--muted);font-size:13px;margin-bottom:8px;}}
code,a{{display:block;border:1px solid var(--line);border-radius:8px;padding:12px;color:var(--accent);text-decoration:none;background:#fbfcfe;}}
ul{{margin:0;padding-left:20px;}}li{{margin:8px 0;}}
.empty{{color:var(--muted);}}
@media(max-width:760px){{.grid,.actions,.links{{grid-template-columns:1fr;}}h1{{font-size:34px;}}}}</style>
</head><body><main class="shell">
<section class="hero">
<h1>\u64cd\u4f5c\u9996\u9875</h1>
<p>\u586b\u5199\u6216\u5bfc\u5165\u771f\u5b9e\u6210\u4ea4\uff0c\u7136\u540e\u8fd0\u884c python -m quant.apps.broker refresh</p></section>
<section class="grid">
<div class="metric"><span>\u65e5\u6d41\u7a0b</span><strong>{status}</strong></div>
<div class="metric"><span>\u7eb8\u9762</span><strong>true</strong></div>
<div class="metric"><span>\u5b9e\u76d8</span><strong>false</strong></div>
<div class="metric"><span>\u6267\u884c</span><strong>{exec_label}</strong></div></section>
<section class="panel"><h2>\u5f00\u59cb\u4f7f\u7528</h2><div class="actions">
<div class="command"><span>\u5b8c\u6574\u6f14\u793a</span><code>python -m quant.apps.start</code></div>
<div class="command"><span>\u65e5\u6d41\u7a0b</span><code>python -m quant.apps.start daily</code></div>
<div class="command"><span>\u81ea\u52a8\u884c\u60c5</span><code>python -m quant.apps.start akshare</code></div>
<div class="command"><span>\u81ea\u52a8\u56de\u6d4b</span><code>python -m quant.apps.start akshare-backtest</code></div>
<div class="command"><span>\u72b6\u6001</span><code>python -m quant.apps.start status</code></div>
<div class="command"><span>\u4f53\u68c0</span><code>python -m quant.apps.start doctor</code></div>
<div class="command"><span>\u7ec3\u4e60\u6210\u4ea4</span><code>python -m quant.apps.start practice-fills</code></div>
<div class="command"><span>\u5bfc\u5165\u6210\u4ea4</span><code>python -m quant.apps.start import-fills</code></div>
<div class="command"><span>\u5f52\u6863</span><code>python -m quant.apps.start snapshot</code></div>
</div></section>
<section class="panel"><h2>\u62a5\u544a</h2><div class="links">
<a href="daily_report.html">\u65e5\u62a5</a>
<a href="operator_doctor.md">\u4f53\u68c0\u62a5\u544a</a>
<a href="execution_dashboard.html">\u6267\u884c\u770b\u677f</a>
<a href="execution_day_end.md">\u65e5\u7ec8\u62a5\u544a</a>
<a href="../monitoring/readiness.md">\u5c31\u7eea\u72b6\u6001</a>
<a href="../monitoring/config_health.md">\u914d\u7f6e\u5065\u5eb7</a>
<a href="manual_fill_template.csv">\u6210\u4ea4\u6a21\u677f</a>
</div></section>
<section class="panel"><h2>\u5feb\u7167</h2>{snap_links_html}</section>
<section class="panel"><h2>\u5173\u6ce8</h2><ul>{warnings_html}</ul></section>
</main></body></html>"""


# ---- Snapshot ----


def latest_snapshot_paths() -> dict[str, Path]:
    rp = ROOT / "research_store" / "reports"
    names = {}
    for fname in [
        "daily_summary.json","daily_report.html","daily_report.md",
        "paper_plan.json","data_quality.json","data_quality.md",
        "risk_guard.md","execution_dashboard.html",
        "execution_day_end.json","execution_day_end.md",
        "manual_fill_template.csv","manual_fill_validation.json",
        "manual_fill_validation.md","manual_reconciliation.json",
        "manual_reconciliation.md","broker_submission.json","broker_submission.md",
    ]:
        p = rp / fname
        if p.exists():
            names[fname] = p
    for fname in ["readiness.md", "config_health.md"]:
        p = ROOT / "research_store" / "monitoring" / fname
        if p.exists():
            names["monitoring_" + fname] = p
    return names

def create_operator_snapshot(
    *,
    output_dir="research_store/archive",
    label="",
    dry_run=False,
) -> SnapshotResult:
    output = Path(output_dir) if not ROOT else ROOT / Path(output_dir)
    now_str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if label:
        slug = label.replace(" ", "-").lower()
        snap_dir = output / f"{now_str}_{slug}"
    else:
        snap_dir = output / now_str
    paths = latest_snapshot_paths()
    if dry_run:
        return SnapshotResult(snap_dir, snap_dir/"snapshot_manifest.json", snap_dir/"snapshot_manifest.md", snap_dir/"snapshot_manifest.html", len(paths), 0)
    snap_dir.mkdir(parents=True, exist_ok=True)
    import shutil, json
    copied = 0
    skipped = 0
    for name, src in paths.items():
        try:
            shutil.copy2(str(src), str(snap_dir / name))
            copied += 1
        except FileNotFoundError:
            skipped += 1
    manifest = {
        "snapshot_ts": datetime.now(UTC).isoformat(),
        "snapshot_dir": str(snap_dir),
        "label": label,
        "files": {n: str(p) for n, p in sorted(paths.items())},
        "copied": copied,
        "skipped": skipped,
    }
    mp = snap_dir / "snapshot_manifest.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    md = snap_dir / "snapshot_manifest.md"
    md.write_text(render_snapshot_manifest_markdown(manifest), encoding="utf-8")
    mh = snap_dir / "snapshot_manifest.html"
    mh.write_text(render_snapshot_manifest_html(manifest), encoding="utf-8")
    return SnapshotResult(snap_dir, mp, md, mh, copied, skipped)


def render_snapshot_manifest_markdown(manifest: dict) -> str:
    parts = ["# Snapshot Manifest", "", f"- Timestamp: {manifest["snapshot_ts"]}", f"- Label: {manifest.get("label", "") or "(none)"}", "", "## Files", ""]
    for name, src in sorted(manifest.get("files", {}).items()):
        parts.append(f"- {name} -> {src}")
    parts.append("")
    parts.append(f"Copied: {manifest["copied"]}, Skipped: {manifest["skipped"]}")
    return "\n".join(parts)

def render_snapshot_manifest_html(manifest: dict) -> str:
    file_rows = ""
    for name, src in sorted(manifest.get("files", {}).items()):
        file_rows += f"<tr><td>{name}</td><td>{src}</td></tr>\n"
    ts = manifest["snapshot_ts"]
    cop = manifest["copied"]
    skp = manifest["skipped"]
    label_val = manifest.get("label", "") or "(none)"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Snapshot Manifest</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;}}
table{{border-collapse:collapse;width:100%;}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left;}}
th{{background:#f5f5f5;}}</style></head><body>
<h1>Snapshot Manifest</h1>
<p>Timestamp: {ts}</p>
<p>Label: {label_val}</p>
<h2>Files</h2><table><tr><th>Name</th><th>Source</th></tr>{file_rows}</table>
<p>Copied: {cop}, Skipped: {skp}</p></body></html>"""


if __name__ == "__main__":
    main()
