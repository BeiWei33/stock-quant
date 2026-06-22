from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def render_backtest_html() -> str:
    payload = _load_latest_payload()
    if not payload:
        return _empty_page()
    if payload.get("mode") == "multi_strategy":
        return _build_multi_strategy_page(payload)
    return _build_single_strategy_page(payload)


def _load_latest_payload() -> dict[str, object]:
    for key in [
        "research_store/reports/akshare_backtest.json",
        "research_store/reports/backtest.json",
        "research_store/reports/sample_backtest.json",
    ]:
        path = ROOT / key
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception:
            continue
    return {}


def _empty_page() -> str:
    return '<!doctype html><html lang="zh-CN"><body><p>暂无回测结果。</p><a href="/">返回</a></body></html>'


def _build_multi_strategy_page(payload: dict[str, object]) -> str:
    metrics = payload.get("metrics", {})
    strategies = payload.get("strategies", [])
    equity = payload.get("equity_curve", [])
    benchmark_equity = payload.get("benchmark_equity_curve", [])
    allocation_history = payload.get("allocation_history", [])
    strategy_name = ", ".join(str(item) for item in strategies) or "多策略组合"
    strategy_return_rows = _strategy_return_rows(payload.get("strategy_returns", []))
    allocation_weight_rows = _allocation_weight_rows(payload.get("allocation_records", []))
    cash_chart = _cash_weight_chart(allocation_history)
    cards = _metric_cards(
        metrics,
        [
            ("年化收益", "annual_return", "pct"),
            ("夏普比率", "sharpe", "decimal"),
            ("最大回撤", "max_drawdown", "pct"),
            ("平均现金权重", "average_cash_weight", "pct"),
        ],
    )
    allocation_rows = _allocation_rows(allocation_history)
    chart = _equity_chart(
        equity,
        benchmark_equity,
        strategy_key="portfolio_equity",
        benchmark_key="benchmark_equity",
    )
    return _page(
        title="多策略组合回测",
        subtitle=f"{html.escape(strategy_name)} | {_period(payload)} | 基准: {html.escape(str(payload.get('benchmark_code', 'equal_weight')))}",
        body=f"""
<div class="grid">{cards}</div>
<section class="panel"><h2>组合净值</h2>{chart}</section>
<section class="panel"><h2>资金分配历史</h2>
<table><thead><tr><th>日期</th><th>策略仓位</th><th>现金权重</th><th>单策略最大权重</th></tr></thead>
<tbody>{allocation_rows}</tbody></table></section>
<section class="panel"><h2>策略收益拆解</h2>
<table><thead><tr><th>策略</th><th>累计收益</th><th>最近日收益</th></tr></thead>
<tbody>{strategy_return_rows}</tbody></table></section>
<section class="panel"><h2>资金权重变化</h2>
<table><thead><tr><th>日期</th><th>权重明细</th></tr></thead>
<tbody>{allocation_weight_rows}</tbody></table></section>
<section class="panel"><h2>现金仓位曲线</h2>{cash_chart}</section>
<section class="panel"><h2>指标明细</h2>{_metrics_table(metrics)}</section>
""",
    )


def _build_single_strategy_page(payload: dict[str, object]) -> str:
    metrics = payload.get("metrics", {})
    strategy = payload.get("strategy", {})
    strategy_id = strategy.get("strategy_id", "momentum_rank") if isinstance(strategy, dict) else "momentum_rank"
    cards = _metric_cards(
        metrics,
        [
            ("年化收益", "annual_return", "pct"),
            ("夏普比率", "sharpe", "decimal"),
            ("最大回撤", "max_drawdown", "pct"),
            ("信息比率", "information_ratio", "decimal"),
        ],
    )
    chart = _equity_chart(
        payload.get("equity_curve", []),
        payload.get("benchmark_equity_curve", []),
        strategy_key="strategy_equity",
        benchmark_key="benchmark_equity",
    )
    rebalance_rows = _rebalance_rows(payload.get("rebalance_records", []))
    return _page(
        title="单策略回测",
        subtitle=f"{html.escape(str(strategy_id))} | {_period(payload)} | 基准: {html.escape(str(payload.get('benchmark_code', 'equal_weight')))}",
        body=f"""
<div class="grid">{cards}</div>
<section class="panel"><h2>策略净值</h2>{chart}</section>
<section class="panel"><h2>指标明细</h2>{_metrics_table(metrics)}</section>
<section class="panel"><h2>调仓记录</h2>
<table><thead><tr><th>日期</th><th>订单数</th><th>成交数</th><th>换手率</th></tr></thead>
<tbody>{rebalance_rows}</tbody></table></section>
""",
    )


def _page(*, title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme:light;--ink:#172033;--muted:#667085;--line:#d7deea;--bg:#f5f7fb;--panel:#fff;--accent:#0f766e; }}
* {{ box-sizing:border-box; }}
body {{ margin:0;font-family:-apple-system,"Microsoft YaHei","PingFang SC",Arial,sans-serif;color:var(--ink);background:var(--bg); }}
.shell {{ width:min(1200px,calc(100% - 32px));margin:28px auto 48px; }}
.back a {{ color:var(--accent);text-decoration:none;font-size:14px; }}
h1 {{ margin:10px 0 4px;font-size:30px; }}
p {{ color:var(--muted); }}
.grid {{ display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0; }}
.card,.panel {{ background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px; }}
.panel {{ margin-bottom:16px; }}
.card span {{ display:block;color:var(--muted);font-size:12px;margin-bottom:6px; }}
.card strong {{ font-size:24px; }}
table {{ width:100%;border-collapse:collapse; }}
th,td {{ padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);font-size:14px; }}
th {{ color:var(--muted);font-size:12px;font-weight:600;background:#fafafa; }}
svg {{ width:100%;height:auto;display:block; }}
@media(max-width:760px){{ .grid{{grid-template-columns:1fr;}} }}
</style></head><body><main class="shell">
<div class="back"><a href="/">返回控制台</a></div>
<h1>{html.escape(title)}</h1>
<p>{subtitle}</p>
{body}
</main></body></html>"""


def _metric_cards(metrics: dict[str, object], items: list[tuple[str, str, str]]) -> str:
    cards = []
    for label, key, kind in items:
        value = float(metrics.get(key, 0.0) or 0.0)
        text = _pct(value) if kind == "pct" else _decimal(value)
        cards.append(f'<div class="card"><span>{html.escape(label)}</span><strong>{text}</strong></div>')
    return "".join(cards)


def _metrics_table(metrics: dict[str, object]) -> str:
    labels = [
        ("总收益", "total_return", "pct"),
        ("基准总收益", "benchmark_total_return", "pct"),
        ("超额收益", "excess_return", "pct"),
        ("年化收益", "annual_return", "pct"),
        ("年化波动", "volatility", "pct"),
        ("夏普比率", "sharpe", "decimal"),
        ("最大回撤", "max_drawdown", "pct"),
        ("信息比率", "information_ratio", "decimal"),
        ("平均现金权重", "average_cash_weight", "pct"),
    ]
    rows = []
    for label, key, kind in labels:
        if key not in metrics:
            continue
        value = float(metrics.get(key, 0.0) or 0.0)
        rows.append(f"<tr><td>{html.escape(label)}</td><td>{_pct(value) if kind == 'pct' else _decimal(value)}</td></tr>")
    if not rows:
        rows.append('<tr><td colspan="2">暂无指标</td></tr>')
    return f"<table><thead><tr><th>指标</th><th>数值</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _allocation_rows(records: object) -> str:
    if not isinstance(records, list) or not records:
        return '<tr><td colspan="4">暂无资金分配记录</td></tr>'
    rows = []
    for record in records[-20:]:
        if not isinstance(record, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(record.get('trade_date', '-')))}</td>"
            f"<td>{_pct(float(record.get('allocated_weight', 0.0) or 0.0), digits=1)}</td>"
            f"<td>{_pct(float(record.get('cash_weight', 0.0) or 0.0), digits=1)}</td>"
            f"<td>{_pct(float(record.get('max_strategy_weight', 0.0) or 0.0), digits=1)}</td>"
            "</tr>"
        )
    return "".join(rows) if rows else '<tr><td colspan="4">暂无资金分配记录</td></tr>'


def _strategy_return_rows(records: object) -> str:
    if not isinstance(records, list) or not records:
        return '<tr><td colspan="3">暂无策略收益数据</td></tr>'
    strategy_ids = sorted(
        {
            str(key)
            for record in records
            if isinstance(record, dict)
            for key in record
            if key not in {"trade_date", "index"}
        }
    )
    rows = []
    for strategy_id in strategy_ids:
        returns = [
            float(record.get(strategy_id, 0.0) or 0.0)
            for record in records
            if isinstance(record, dict)
        ]
        cumulative = 1.0
        for value in returns:
            cumulative *= 1.0 + value
        latest = returns[-1] if returns else 0.0
        rows.append(
            "<tr>"
            f"<td>{html.escape(strategy_id)}</td>"
            f"<td>{_pct(cumulative - 1.0)}</td>"
            f"<td>{_pct(latest)}</td>"
            "</tr>"
        )
    return "".join(rows) if rows else '<tr><td colspan="3">暂无策略收益数据</td></tr>'


def _allocation_weight_rows(records: object) -> str:
    if not isinstance(records, list) or not records:
        return '<tr><td colspan="2">暂无权重记录</td></tr>'
    rows = []
    for record in records[-20:]:
        if not isinstance(record, dict):
            continue
        weights = record.get("weights", [])
        if not isinstance(weights, list):
            weights = []
        parts = []
        for item in weights:
            if not isinstance(item, dict):
                continue
            strategy_id = str(item.get("strategy_id", "-"))
            weight = float(item.get("capital_weight", 0.0) or 0.0)
            parts.append(f"{html.escape(strategy_id)} {_pct(weight, digits=1)}")
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(record.get('allocation_date', '-')))}</td>"
            f"<td>{' / '.join(parts) if parts else '-'}</td>"
            "</tr>"
        )
    return "".join(rows) if rows else '<tr><td colspan="2">暂无权重记录</td></tr>'


def _cash_weight_chart(records: object) -> str:
    if not isinstance(records, list) or not records:
        return "<p>暂无现金仓位数据</p>"
    points = [
        (str(record.get("trade_date", "")), float(record.get("cash_weight", 0.0) or 0.0))
        for record in records
        if isinstance(record, dict)
    ]
    if not points:
        return "<p>暂无现金仓位数据</p>"
    return _line_chart(points, low=0.0, high=max(1.0, max(value for _, value in points)))


def _rebalance_rows(records: object) -> str:
    if not isinstance(records, list) or not records:
        return '<tr><td colspan="4">暂无调仓记录</td></tr>'
    rows = []
    for record in records[-20:]:
        if not isinstance(record, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(record.get('trade_date', '-')))}</td>"
            f"<td>{int(record.get('order_count', 0) or 0)}</td>"
            f"<td>{int(record.get('filled_count', 0) or 0)}</td>"
            f"<td>{_pct(float(record.get('turnover', 0.0) or 0.0), digits=1)}</td>"
            "</tr>"
        )
    return "".join(rows) if rows else '<tr><td colspan="4">暂无调仓记录</td></tr>'


def _equity_chart(
    equity: object,
    benchmark_equity: object,
    *,
    strategy_key: str,
    benchmark_key: str,
) -> str:
    strategy = _series_points(equity, strategy_key)
    benchmark = _series_points(benchmark_equity, benchmark_key)
    values = [value for _, value in strategy + benchmark]
    if not values:
        return "<p>暂无净值数据</p>"
    width, height, left, top = 720, 240, 54, 18
    inner_width, inner_height = width - 80, height - 52
    low, high = min(values), max(values)
    if high == low:
        high = low + 1.0
    padding = (high - low) * 0.05

    def path(points: list[tuple[str, float]]) -> str:
        if not points:
            return ""
        max_index = max(len(points) - 1, 1)
        chunks = []
        for idx, (_, value) in enumerate(points):
            x = left + idx * inner_width / max_index
            y = top + inner_height - ((value - low + padding) / (high - low + padding * 2) * inner_height)
            chunks.append(("M" if idx == 0 else "L") + f"{x:.1f},{y:.1f}")
        return " ".join(chunks)

    labels = "".join(
        f"<text x='{left - 8}' y='{top + inner_height - ratio * inner_height + 4:.1f}' text-anchor='end' fill='#667085' font-size='11'>{low + (high - low) * ratio:.0f}</text>"
        for ratio in [0, 0.25, 0.5, 0.75, 1.0]
    )
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect x="{left}" y="{top}" width="{inner_width}" height="{inner_height}" fill="none" stroke="#d7deea"/>
{labels}
<path d="{path(strategy)}" fill="none" stroke="#0f766e" stroke-width="2"/>
<path d="{path(benchmark)}" fill="none" stroke="#667085" stroke-dasharray="4,3" stroke-width="1.5"/>
</svg>"""


def _line_chart(points: list[tuple[str, float]], *, low: float, high: float) -> str:
    width, height, left, top = 720, 180, 54, 18
    inner_width, inner_height = width - 80, height - 52
    if high <= low:
        high = low + 1.0
    max_index = max(len(points) - 1, 1)
    chunks = []
    for idx, (_, value) in enumerate(points):
        x = left + idx * inner_width / max_index
        y = top + inner_height - ((value - low) / (high - low) * inner_height)
        chunks.append(("M" if idx == 0 else "L") + f"{x:.1f},{y:.1f}")
    labels = "".join(
        f"<text x='{left - 8}' y='{top + inner_height - ratio * inner_height + 4:.1f}' text-anchor='end' fill='#667085' font-size='11'>{_pct(low + (high - low) * ratio, digits=0)}</text>"
        for ratio in [0, 0.5, 1.0]
    )
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect x="{left}" y="{top}" width="{inner_width}" height="{inner_height}" fill="none" stroke="#d7deea"/>
{labels}
<path d="{' '.join(chunks)}" fill="none" stroke="#b45309" stroke-width="2"/>
</svg>"""


def _series_points(records: object, value_key: str) -> list[tuple[str, float]]:
    if not isinstance(records, list):
        return []
    points = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if value_key not in record:
            continue
        points.append((str(record.get("trade_date", "")), float(record.get(value_key, 0.0) or 0.0)))
    return points


def _period(payload: dict[str, object]) -> str:
    start = str(payload.get("start_date") or "")
    end = str(payload.get("end_date") or "")
    if start or end:
        return f"{start or '-'} ~ {end or '-'}"
    return "-"


def _pct(value: float, *, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


def _decimal(value: float) -> str:
    return f"{value:.4f}"
