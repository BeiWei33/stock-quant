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
    assert "多策略组合回测" in html
    assert "参数实验记录" in html
    assert 'name="multi_strategy"' in html
    assert 'name="allocation_method"' in html
    assert 'name="experiment_name"' in html
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
        return _web_result(action, command)

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


def test_run_akshare_backtest_builds_multi_strategy_command(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run_command(action: str, command: list[str]):
        seen["action"] = action
        seen["command"] = command
        return _web_result(action, command)

    monkeypatch.setattr(control, "run_command", fake_run_command)

    result = control.run_akshare_backtest(
        start_date="2024-01-01",
        end_date="2024-12-31",
        rebalance="monthly",
        limit="10",
        multi_strategy="momentum_rank,quality_rank",
        allocation_method="equal",
        target_volatility="0.10",
        max_strategy_weight="0.50",
        experiment_name="risk parity 10 vol",
    )

    assert result.status == "OK"
    command = seen["command"]
    assert seen["action"] == "akshare-backtest"
    assert "--multi-strategy" in command
    assert "momentum_rank,quality_rank" in command
    assert "--allocation-method" in command
    assert "equal" in command
    assert "--target-volatility" in command
    assert "0.10" in command
    assert "--max-strategy-weight" in command
    assert "0.50" in command


def test_save_backtest_experiment_writes_json_and_markdown(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(control, "ROOT", tmp_path)
    report = tmp_path / "research_store/reports/akshare_backtest.json"
    _write_json(
        report,
        {
            "mode": "multi_strategy",
            "strategies": ["momentum_rank", "quality_rank"],
            "metrics": {
                "total_return": 0.12,
                "annual_return": 0.10,
                "sharpe": 1.23,
                "max_drawdown": -0.08,
                "average_cash_weight": 0.20,
            },
            "allocation": {"method": "risk_parity"},
        },
    )

    path = control.save_backtest_experiment(
        params={
            "experiment_name": "risk parity 12 vol",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "multi_strategy": "momentum_rank,quality_rank",
            "target_volatility": "0.12",
            "max_strategy_weight": "0.60",
        },
        result=_web_result("akshare-backtest", ["python"]),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload[0]["experiment_name"] == "risk parity 12 vol"
    assert payload[0]["strategies"] == ["momentum_rank", "quality_rank"]
    assert payload[0]["metrics"]["sharpe"] == 1.23
    markdown = (tmp_path / "research_store/reports/backtest_experiments.md").read_text(encoding="utf-8")
    assert "参数实验记录" in markdown
    assert "risk parity 12 vol" in markdown
    assert "momentum_rank, quality_rank" in markdown


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
        return _web_result(action, command)

    monkeypatch.setattr(control, "run_command", fake_run_command)

    result = control.import_uploaded_fills("fills.csv", b"a,b\n1,2\n", skip_refresh=True)

    assert result.status == "OK"
    assert seen["action"] == "import-fills"
    command = seen["command"]
    assert "import-fills" in command
    assert "--skip-refresh" in command
    uploads = list((tmp_path / "research_store/web_uploads").glob("*fills.csv"))
    assert len(uploads) == 1


def _web_result(action: str, command: list[str]) -> control.WebRunResult:
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


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
