from __future__ import annotations

import json

from quant.core.monitoring.notification import (
    DailyNotificationBuilder,
    FileNotificationSink,
    render_text,
)


def test_daily_notification_builder_creates_info_message(tmp_path) -> None:
    summary_path = tmp_path / "daily_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "trade_date": "2024-09-09",
                "run_id": "run-1",
                "run_status": "SUCCESS",
                "ok": True,
                "collected_stocks": 30,
                "collected_daily_bars": 5400,
                "order_count": 3,
                "rejected_order_count": 0,
                "fill_count": 3,
                "fill_rejected_count": 0,
                "snapshot": {
                    "total_asset": 999910.54,
                    "cash": 701719.13,
                    "market_value": 298191.41,
                    "total_position_ratio": 0.2982,
                    "daily_return": -0.0001,
                    "drawdown": -0.0001,
                },
                "health_checks": [{"name": "daily_bars", "ok": True, "detail": "count=5400"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    message = DailyNotificationBuilder(
        summary_path=summary_path,
        report_markdown_path=tmp_path / "daily_report.md",
    ).build()

    assert message.level == "INFO"
    assert "Quant Daily 2024-09-09 SUCCESS" in message.title
    assert "Total Asset: 999,910.54" in message.body
    assert "Markdown Report" in render_text(message)


def test_daily_notification_marks_failed_health_check_as_warning(tmp_path) -> None:
    summary_path = tmp_path / "daily_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "trade_date": "2024-09-09",
                "run_status": "CHECK",
                "ok": False,
                "health_checks": [
                    {"name": "research_report_exists", "ok": False, "detail": "missing"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    message = DailyNotificationBuilder(summary_path=summary_path).build()

    assert message.level == "WARNING"
    assert "Failed Health Checks" in message.body
    assert "research_report_exists" in message.body


def test_file_notification_sink_writes_payload(tmp_path) -> None:
    summary_path = tmp_path / "daily_summary.json"
    summary_path.write_text(
        json.dumps({"trade_date": "2024-09-09", "run_status": "SUCCESS", "ok": True}),
        encoding="utf-8",
    )
    message = DailyNotificationBuilder(summary_path=summary_path).build()
    output = FileNotificationSink(tmp_path / "notification.json").send(message)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["level"] == "INFO"
    assert payload["text"].startswith("[INFO] Quant Daily")
