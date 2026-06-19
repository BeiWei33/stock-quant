from __future__ import annotations

from quant.apps.schedule import build_cron_entry, build_windows_task_command


def test_build_windows_task_command_contains_daily_module() -> None:
    command = build_windows_task_command(
        task_name="QuantDaily",
        time_text="17:30",
        python_cmd="python",
        working_dir="D:/quant",
        daily_args="--source csv",
    )

    assert "schtasks /Create" in command
    assert 'cd /d ""D:/quant""' in command
    assert "python -m quant.apps.daily --source csv" in command


def test_build_cron_entry_contains_time_and_daily_module() -> None:
    entry = build_cron_entry(
        time_text="17:30",
        python_cmd="python",
        working_dir="/opt/quant",
        daily_args="--source csv",
        log_path="logs/daily.log",
    )

    assert entry.startswith("30 17 * * 1-5")
    assert 'cd "/opt/quant"' in entry
    assert "python -m quant.apps.daily --source csv" in entry


def test_schedule_config_args_are_short() -> None:
    command = build_windows_task_command(
        task_name="QuantDaily",
        time_text="17:30",
        python_cmd="python",
        working_dir=".",
        daily_args="--config config/daily.yaml",
    )

    assert "python -m quant.apps.daily --config config/daily.yaml" in command
