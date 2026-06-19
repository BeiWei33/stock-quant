from __future__ import annotations

import json

from quant.core.web import control


def test_web_console_renders_chinese_dashboard(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(control, "ROOT", tmp_path)
    _write_json(tmp_path / "research_store/reports/daily_summary.json", {"run_status": "SUCCESS"})
    _write_json(
        tmp_path / "research_store/monitoring/readiness.json",
        {"paper_ready": True, "live_ready": False, "status": "PAPER_READY", "checks": []},
    )
    _write_json(tmp_path / "research_store/reports/execution_day_end.json", {"status": "READY"})
    _write_json(tmp_path / "research_store/monitoring/config_health.json", {"status": "OK"})

    html = control.render_console_html()

    assert "本地控制台" in html
    assert "上传真实成交 CSV" in html
    assert "全市场选股" in html
    assert "AkShare 全市场回测" in html
    assert 'name="start_date"' in html
    assert "刷新执行链路" in html
    assert "/file/research_store/reports/execution_dashboard.html" in html


def test_action_command_is_allowlisted() -> None:
    assert control._action_command("doctor")[-1] == "doctor"
    assert control._action_command("akshare")[-1] == "akshare"

    try:
        control._action_command("bad")
    except ValueError as exc:
        assert "unsupported action" in str(exc)
    else:
        raise AssertionError("expected unsupported action to raise")


def test_run_akshare_backtest_builds_start_command(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_command(action: str, command: list[str]):
        seen["action"] = action
        seen["command"] = command
        return control.WebRunResult(
            run_id="run",
            action=action,
            status="OK",
            return_code=0,
            command=command,
            started_at="",
            ended_at="",
            stdout="",
            stderr="",
            log_path="log",
            json_path="json",
        )

    monkeypatch.setattr(control, "run_command", fake_run_command)

    result = control.run_akshare_backtest(
        start_date="2024-01-01",
        end_date="2024-12-31",
        rebalance="monthly",
        limit="10",
    )

    assert result.status == "OK"
    assert seen["action"] == "akshare-backtest"
    command = seen["command"]
    assert "akshare-backtest" in command
    assert "2024-01-01" in command
    assert "2024-12-31" in command
    assert "--limit" in command
    assert "10" in command


def test_file_response_path_is_limited_to_report_roots(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(control, "ROOT", tmp_path)
    report = tmp_path / "research_store/reports/report.html"
    report.parent.mkdir(parents=True)
    report.write_text("ok", encoding="utf-8")

    assert control.file_response_path("/file/research_store/reports/report.html") == report

    secret = tmp_path / "secret.txt"
    secret.write_text("no", encoding="utf-8")
    try:
        control.file_response_path("/file/secret.txt")
    except PermissionError:
        pass
    else:
        raise AssertionError("expected path outside report roots to be blocked")


def test_import_uploaded_fills_saves_upload_and_runs_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(control, "ROOT", tmp_path)
    monkeypatch.setattr(control, "UPLOAD_DIR", tmp_path / "research_store/web_uploads")
    monkeypatch.setattr(control, "RUN_DIR", tmp_path / "research_store/web_runs")
    seen: dict[str, object] = {}

    def fake_run_command(action: str, command: list[str]):
        seen["action"] = action
        seen["command"] = command
        return control.WebRunResult(
            run_id="run",
            action=action,
            status="OK",
            return_code=0,
            command=command,
            started_at="",
            ended_at="",
            stdout="",
            stderr="",
            log_path="log",
            json_path="json",
        )

    monkeypatch.setattr(control, "run_command", fake_run_command)

    result = control.import_uploaded_fills("fills.csv", b"a,b\n1,2\n", skip_refresh=True)

    assert result.status == "OK"
    assert seen["action"] == "import-fills"
    command = seen["command"]
    assert "import-fills" in command
    assert "--skip-refresh" in command
    uploads = list((tmp_path / "research_store/web_uploads").glob("*fills.csv"))
    assert len(uploads) == 1


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
