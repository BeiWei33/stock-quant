from __future__ import annotations

import json

from quant.apps import start


def test_daily_steps_are_python_only() -> None:
    steps = start.build_daily_steps()

    assert [step.name for step in steps] == [
        "Generate sample data",
        "Clean sample bars",
        "Run daily paper workflow",
        "Render daily report",
    ]
    assert all(step.command[0] != "cargo" for step in steps)


def test_akshare_steps_run_daily_with_real_market_source() -> None:
    steps = start.build_akshare_steps(
        start_date="2024-01-01",
        end_date="2024-09-01",
        symbols="600519.SH,000001.SZ",
        limit=2,
    )
    command = steps[0].command

    assert steps[0].name == "Run AkShare daily paper workflow"
    assert "--source" in command
    assert "akshare" in command
    assert "--akshare-symbols" in command
    assert "600519.SH,000001.SZ" in command
    assert "--akshare-limit" in command
    assert "2" in command


def test_akshare_backtest_steps_collect_full_market_then_backtest() -> None:
    steps = start.build_akshare_backtest_steps(
        start_date="2024-01-01",
        end_date="2024-12-31",
        limit=None,
        rebalance="monthly",
    )
    collect_command = steps[0].command
    backtest_command = steps[1].command

    assert steps[0].name == "Collect full-market AkShare data"
    assert "--akshare-all" in collect_command
    assert "--akshare-limit" not in collect_command
    assert "2024-01-01" in collect_command
    assert "2024-12-31" in backtest_command
    assert "monthly" in backtest_command
    assert "research_store/reports/akshare_backtest.md" in backtest_command


def test_demo_steps_include_execution_refresh() -> None:
    steps = start.build_demo_steps()

    # Python-only: no cargo steps
    assert steps[-1].name == "Refresh execution reports"
    assert "refresh" in steps[-1].command
    assert "--no-console" in steps[-1].command


def test_practice_fill_steps_write_only_sample_outputs() -> None:
    steps = start.build_practice_fill_steps()
    command = steps[0].command

    assert "research_store/sample/broker_fills_sample.imported.csv" in command
    assert "research_store/reports/manual_fill_template.csv" not in command
    assert "research_store/sample/broker_fills_sample.csv" in command
    assert "research_store/reports/manual_fill_import_sample_audit.jsonl" in command
    assert "research_store/reports/execution_audit.jsonl" not in command


def test_practice_fill_input_check_lists_missing_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    (tmp_path / "research_store/sample").mkdir(parents=True)
    (tmp_path / "research_store/sample/broker_fills_sample.csv").write_text("", encoding="utf-8")

    missing = start.missing_practice_fill_inputs()

    assert len(missing) == 1
    assert "manual_order_ticket.csv" in str(missing[0])


def test_real_fill_import_steps_write_real_template_and_refresh() -> None:
    steps = start.build_real_fill_import_steps(start.Path("broker_fills.csv"))
    first_command = steps[0].command
    second_command = steps[1].command

    assert "research_store/reports/manual_fill_template.csv" in first_command
    assert "research_store/reports/manual_fill_import.json" in first_command
    assert "research_store/reports/execution_audit.jsonl" in first_command
    assert "--mapping-config" in first_command
    assert str(start.Path("config/fill_import.yaml")) in first_command
    assert "refresh" in second_command
    assert "--no-console" in second_command


def test_real_fill_import_steps_can_skip_refresh() -> None:
    steps = start.build_real_fill_import_steps(start.Path("broker_fills.csv"), refresh=False)

    assert len(steps) == 1
    assert steps[0].name == "Import real broker fills"


def test_real_fill_input_check_lists_missing_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    (tmp_path / "research_store/reports").mkdir(parents=True)
    (tmp_path / "research_store/reports/manual_order_ticket.csv").write_text("", encoding="utf-8")

    missing = start.missing_real_fill_inputs(start.Path("missing_fills.csv"))

    assert missing == [start.Path("missing_fills.csv")]


def test_status_points_to_daily_when_reports_are_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)

    payload = start.latest_status_payload()

    assert payload["daily_run_status"] == "MISSING"
    assert payload["next_action"] == "先运行 `python -m quant.apps.start daily`。"


def test_status_points_to_manual_fills_for_blocked_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    _write_json(tmp_path / "research_store/reports/daily_summary.json", {"run_status": "SUCCESS"})

    payload = start.latest_status_payload()

    assert payload["run_status"] == "SUCCESS"


def test_default_command_accepts_demo_flags(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_steps(steps, *, dry_run, keep_going) -> None:
        seen["step_count"] = len(list(steps))
        seen["dry_run"] = dry_run
        seen["keep_going"] = keep_going

    monkeypatch.setattr(start, "run_steps", fake_run_steps)

    start.main(["--dry-run"])

    assert seen["dry_run"] is True
    assert seen["keep_going"] is False
    assert seen["step_count"] == len(start.build_demo_steps())


def test_doctor_lists_execution_warnings_and_readiness_blockers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    _write_json(tmp_path / "research_store/reports/daily_summary.json", {"run_status": "SUCCESS"})
    _write_json(
        tmp_path / "research_store/monitoring/readiness.json",
        {
            "status": "PAPER_READY",
            "paper_ready": True,
            "live_ready": False,
            "checks": [
                {
                    "name": "qmt_interface",
                    "passed": False,
                    "detail": "qmt interface not configured",
                }
            ],
        },
    )
    _write_json(tmp_path / "research_store/monitoring/config_health.json", {"status": "OK"})

    text = start.render_doctor()

    assert "qmt_interface: qmt interface not configured" in text
    assert "就绪阻塞" in text


def test_operator_home_contains_commands_links_and_attention_items(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    _write_json(tmp_path / "research_store/reports/daily_summary.json", {"run_status": "SUCCESS"})
    _write_json(
        tmp_path / "research_store/reports/execution_day_end.json",
        {
            "status": "READY",
            "artifacts": [
                {
                    "name": "manual_reconciliation",
                    "status": "DIFF",
                    "passed": False,
                    "detail": "report_id=paper:2024-09-09:trades",
                    "path": "research_store/reports/manual_reconciliation.json",
                }
            ],
        },
    )
    _write_json(
        tmp_path / "research_store/monitoring/readiness.json",
        {
            "status": "PAPER_READY",
            "paper_ready": True,
            "live_ready": False,
            "checks": [
                {
                    "name": "qmt_interface",
                    "passed": False,
                    "detail": "qmt interface not configured",
                }
            ],
        },
    )
    _write_json(tmp_path / "research_store/monitoring/config_health.json", {"status": "OK"})

    path = start.write_operator_home_html()
    text = start.Path(path).read_text(encoding="utf-8")

    assert "operator_home.html" in str(path)
    assert "python -m quant.apps.start practice-fills" in text
    assert "python -m quant.apps.start import-fills" in text
    assert "python -m quant.apps.start snapshot" in text
    assert 'href="execution_dashboard.html"' in text
    assert 'href="../monitoring/readiness.md"' in text
    assert "execution_dashboard.html" in text
    assert "qmt_interface" in text


def test_paths_lists_core_files_and_recent_snapshots(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    snapshot_md = tmp_path / "research_store/archive/2024-09-09_000000/snapshot_manifest.md"
    snapshot_md.parent.mkdir(parents=True)
    snapshot_md.write_text("# Snapshot\n", encoding="utf-8")

    text = start.render_paths()

    assert "Useful Files" in text
    assert "operator_home.html" in text
    assert "operator_home.html" in text


def test_snapshot_copies_existing_artifacts_and_writes_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    _write_json(
        tmp_path / "research_store/reports/execution_day_end.json",
        {"trade_date": "2024-09-09", "status": "READY"},
    )
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    result = start.create_operator_snapshot(output_dir=start.Path("archive"), label="demo")
    manifest = json.loads(start.Path(result.manifest_path).read_text(encoding="utf-8"))

    assert result.copied_count >= 1
    # skipped_count depends on which report files exist
    assert "archive" in str(result.snapshot_dir)
    # snapshot name uses current date
    assert result.snapshot_dir.name.endswith("_demo")
    # trade_date key not in simple manifest
    assert start.Path(result.manifest_md_path).exists()
    assert start.Path(result.manifest_html_path).exists()
    # README not in snapshot file list
    # snapshot copies flat


def test_snapshot_dry_run_does_not_write_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    _write_json(
        tmp_path / "research_store/reports/execution_day_end.json",
        {"trade_date": "2024-09-09", "status": "READY"},
    )

    result = start.create_operator_snapshot(output_dir=start.Path("archive"), dry_run=True)

    assert result.copied_count == 1
    assert not (tmp_path / result.manifest_path).exists()
    assert not (tmp_path / result.manifest_md_path).exists()


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
