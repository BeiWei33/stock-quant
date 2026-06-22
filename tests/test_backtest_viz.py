from __future__ import annotations

import json

from quant.core.web import backtest_viz


def test_backtest_viz_renders_multi_strategy_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backtest_viz, "ROOT", tmp_path)
    report = tmp_path / "research_store/reports/akshare_backtest.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "mode": "multi_strategy",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "benchmark_code": "equal_weight",
                "strategies": ["momentum_rank", "quality_rank"],
                "metrics": {
                    "annual_return": 0.12,
                    "sharpe": 1.5,
                    "max_drawdown": -0.08,
                    "average_cash_weight": 0.2,
                },
                "equity_curve": [
                    {"trade_date": "2024-01-01", "portfolio_equity": 1_000_000},
                    {"trade_date": "2024-01-02", "portfolio_equity": 1_010_000},
                ],
                "benchmark_equity_curve": [
                    {"trade_date": "2024-01-01", "benchmark_equity": 1_000_000},
                    {"trade_date": "2024-01-02", "benchmark_equity": 1_005_000},
                ],
                "allocation_history": [
                    {
                        "trade_date": "2024-01-02",
                        "allocated_weight": 0.8,
                        "cash_weight": 0.2,
                        "max_strategy_weight": 0.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    html = backtest_viz.render_backtest_html()

    assert "多策略组合回测" in html
    assert "momentum_rank, quality_rank" in html
    assert "平均现金权重" in html
    assert "资金分配历史" in html
    assert "20.0%" in html
