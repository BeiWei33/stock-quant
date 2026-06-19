from __future__ import annotations

import argparse


DEFAULT_DAILY_ARGS = (
    "--source csv --stocks research_store/sample/stocks.csv "
    "--bars research_store/sample/daily_bar.csv "
    "--market-sqlite research_store/market_data.sqlite3 "
    "--paper-sqlite research_store/paper_trading.sqlite3 "
    "--output research_store/reports/daily_summary.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate scheduler commands for workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    windows = subparsers.add_parser("windows", help="Generate a Windows Task Scheduler command.")
    windows.add_argument("--task-name", default="PersonalQuantDaily")
    windows.add_argument("--time", default="17:30")
    windows.add_argument("--python", default="python")
    windows.add_argument("--working-dir", default=".")
    windows.add_argument("--config")
    windows.add_argument("--daily-args", default=DEFAULT_DAILY_ARGS)

    cron = subparsers.add_parser("cron", help="Generate a cron entry.")
    cron.add_argument("--time", default="17:30")
    cron.add_argument("--python", default="python")
    cron.add_argument("--working-dir", default=".")
    cron.add_argument("--config")
    cron.add_argument("--daily-args", default=DEFAULT_DAILY_ARGS)
    cron.add_argument("--weekdays-only", action="store_true", default=True)
    cron.add_argument("--log", default="logs/daily.log")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    daily_args = f"--config {args.config}" if getattr(args, "config", None) else args.daily_args
    if args.command == "windows":
        print(build_windows_task_command(args.task_name, args.time, args.python, args.working_dir, daily_args))
    elif args.command == "cron":
        print(build_cron_entry(args.time, args.python, args.working_dir, daily_args, args.log, args.weekdays_only))


def build_windows_task_command(
    task_name: str,
    time_text: str,
    python_cmd: str,
    working_dir: str,
    daily_args: str,
) -> str:
    command = f'cmd /c \\"cd /d ""{working_dir}"" && {python_cmd} -m quant.apps.daily {daily_args}\\"'
    return (
        f'schtasks /Create /TN "{task_name}" /SC DAILY /ST {time_text} '
        f'/TR "{command}" /F'
    )


def build_cron_entry(
    time_text: str,
    python_cmd: str,
    working_dir: str,
    daily_args: str,
    log_path: str,
    weekdays_only: bool = True,
) -> str:
    hour, minute = _parse_time(time_text)
    day_of_week = "1-5" if weekdays_only else "*"
    command = (
        f'cd "{working_dir}" && {python_cmd} -m quant.apps.daily {daily_args} '
        f'>> "{log_path}" 2>&1'
    )
    return f"{minute} {hour} * * {day_of_week} {command}"


def _parse_time(time_text: str) -> tuple[int, int]:
    parts = time_text.split(":")
    if len(parts) != 2:
        raise ValueError("time must be HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time must be HH:MM")
    return hour, minute


if __name__ == "__main__":
    main()
