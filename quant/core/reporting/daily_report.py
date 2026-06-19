from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant.core.models import PortfolioSnapshot
from quant.core.persistence.sqlite_store import SqliteStore


@dataclass(frozen=True)
class DailyReportResult:
    trade_date: str
    markdown_path: Path
    html_path: Path | None = None


class DailyReportGenerator:
    """Render a human-readable daily report from workflow and paper-account artifacts."""

    def __init__(
        self,
        *,
        summary_path: Path,
        paper_store_path: Path,
        account_id: str = "paper",
        workflow_name: str = "daily",
    ) -> None:
        self.summary_path = summary_path
        self.paper_store_path = paper_store_path
        self.account_id = account_id
        self.workflow_name = workflow_name

    def generate(
        self,
        *,
        markdown_path: Path,
        html_path: Path | None = None,
    ) -> DailyReportResult:
        summary = _read_json(self.summary_path)
        trade_date = _trade_date(summary)
        store = SqliteStore(self.paper_store_path)
        store.init_schema()

        snapshot = self._snapshot(summary, store, trade_date)
        orders = store.load_order_intents(self.account_id, trade_date)
        fills = store.load_order_fills(self.account_id, trade_date)
        positions = store.load_positions(self.account_id, trade_date)
        risk_checks = store.load_order_risk_checks(self.account_id, trade_date)
        reconciliations = store.load_reconciliation_reports(self.account_id, trade_date)
        latest_run = store.load_latest_workflow_run(self.workflow_name)
        alpha_report = _read_optional_json(summary.get("research_json_path"))

        markdown = self._render_markdown(
            summary=summary,
            trade_date=trade_date,
            snapshot=snapshot,
            orders=orders,
            fills=fills,
            positions=positions,
            risk_checks=risk_checks,
            reconciliations=reconciliations,
            latest_run=latest_run.to_dict() if latest_run else {},
            alpha_report=alpha_report,
        )
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")

        if html_path is not None:
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(_markdown_to_html(markdown), encoding="utf-8")

        return DailyReportResult(
            trade_date=trade_date,
            markdown_path=markdown_path,
            html_path=html_path,
        )

    def _snapshot(
        self, summary: dict[str, Any], store: SqliteStore, trade_date: str
    ) -> dict[str, Any]:
        summary_snapshot = summary.get("snapshot")
        if isinstance(summary_snapshot, dict):
            return summary_snapshot
        stored = store.load_portfolio_snapshot(self.account_id, trade_date)
        return stored.to_dict() if isinstance(stored, PortfolioSnapshot) else {}

    def _render_markdown(
        self,
        *,
        summary: dict[str, Any],
        trade_date: str,
        snapshot: dict[str, Any],
        orders: pd.DataFrame,
        fills: pd.DataFrame,
        positions: pd.DataFrame,
        risk_checks: pd.DataFrame,
        reconciliations: pd.DataFrame,
        latest_run: dict[str, Any],
        alpha_report: dict[str, Any],
    ) -> str:
        lines: list[str] = [
            f"# 每日量化报告 - {trade_date}",
            "",
            f"> 数据源说明：{_data_source_note(summary)}",
            "",
            f"来源摘要：`{self.summary_path}`",
            "",
            "## 流程概览",
            _table(
                ["项目", "值"],
                [
                    ["账户", self.account_id],
                    ["运行状态", summary.get("run_status", latest_run.get("status", "-"))],
                    ["运行 ID", summary.get("run_id", latest_run.get("run_id", "-"))],
                    ["摘要是否正常", summary.get("ok", "-")],
                    ["股票数", summary.get("collected_stocks", 0)],
                    ["日线数量", summary.get("collected_daily_bars", 0)],
                    ["基准日线数量", summary.get("collected_benchmark_bars", 0)],
                    ["数据质量级别", summary.get("data_quality_level", "-")],
                    ["订单数", summary.get("order_count", len(orders))],
                    ["拒绝订单数", summary.get("rejected_order_count", 0)],
                    ["成交数", summary.get("fill_count", len(fills))],
                    ["拒绝成交数", summary.get("fill_rejected_count", 0)],
                ],
            ),
            "",
            "## 健康检查",
            self._health_table(summary.get("health_checks", [])),
            "",
            "## 组合资产",
            self._portfolio_table(snapshot),
            "",
            "## 订单",
            self._orders_table(orders),
            "",
            "## 成交",
            self._fills_table(fills),
            "",
            "## 风控检查",
            self._risk_table(risk_checks),
            "",
            "## 对账",
            self._reconciliation_table(reconciliations),
            "",
            "## 持仓",
            self._positions_table(positions),
            "",
            "## Alpha 研究",
            self._alpha_table(alpha_report),
            "",
            "## 产物",
            _table(
                ["产物", "路径"],
                [
                    ["研究 JSON", summary.get("research_json_path", "-")],
                    ["研究 Markdown", summary.get("research_markdown_path", "-")],
                    ["数据质量 JSON", summary.get("data_quality_json_path", "-")],
                    ["数据质量 Markdown", summary.get("data_quality_markdown_path", "-")],
                    ["日摘要", self.summary_path],
                    ["纸面账户 SQLite", self.paper_store_path],
                ],
            ),
            "",
        ]
        return "\n".join(lines)

    def _health_table(self, checks: object) -> str:
        if not isinstance(checks, list) or not checks:
            return "_没有记录健康检查。_"
        return _table(
            ["检查项", "通过", "详情"],
            [
                [
                    check.get("name", "-") if isinstance(check, dict) else "-",
                    check.get("ok", "-") if isinstance(check, dict) else "-",
                    check.get("detail", "") if isinstance(check, dict) else "",
                ]
                for check in checks
            ],
        )

    def _portfolio_table(self, snapshot: dict[str, Any]) -> str:
        if not snapshot:
            return "_没有记录组合快照。_"
        return _table(
            ["指标", "值"],
            [
                ["总资产", _money(snapshot.get("total_asset"))],
                ["现金", _money(snapshot.get("cash"))],
                ["市值", _money(snapshot.get("market_value"))],
                ["仓位比例", _percent(snapshot.get("total_position_ratio"))],
                ["日收益", _percent(snapshot.get("daily_return"))],
                ["累计收益", _percent(snapshot.get("cum_return"))],
                ["回撤", _percent(snapshot.get("drawdown"))],
                ["超额收益", _percent(snapshot.get("excess_return"))],
            ],
        )

    def _orders_table(self, orders: pd.DataFrame) -> str:
        if orders.empty:
            return "_没有记录订单。_"
        rows = []
        for row in orders.itertuples(index=False):
            rows.append(
                [
                    row.ts_code,
                    row.side,
                    row.quantity,
                    _money(row.price),
                    _percent(row.target_weight),
                    row.status,
                    row.reason,
                ]
            )
        return _table(["代码", "方向", "数量", "价格", "目标权重", "状态", "原因"], rows)

    def _fills_table(self, fills: pd.DataFrame) -> str:
        if fills.empty:
            return "_没有记录成交。_"
        rows = []
        for row in fills.itertuples(index=False):
            rows.append(
                [
                    row.ts_code,
                    row.side,
                    row.quantity,
                    _money(row.price),
                    _money(row.amount),
                    _money(row.fee),
                    _money(row.tax),
                ]
            )
        return _table(["代码", "方向", "数量", "价格", "金额", "手续费", "税费"], rows)

    def _risk_table(self, risk_checks: pd.DataFrame) -> str:
        if risk_checks.empty:
            return "_没有记录风控检查。_"
        rows = []
        for row in risk_checks.itertuples(index=False):
            rows.append([row.ts_code, row.side, row.allowed, row.reasons or ""])
        return _table(["代码", "方向", "是否允许", "原因"], rows)

    def _reconciliation_table(self, reports: pd.DataFrame) -> str:
        if reports.empty:
            return "_没有记录对账报告。_"
        rows = []
        for row in reports.itertuples(index=False):
            rows.append(
                [
                    row.report_id,
                    row.status,
                    row.local_count,
                    row.broker_count,
                    _reconciliation_diff_count(row.detail),
                ]
            )
        return _table(["报告", "状态", "本地数量", "券商数量", "差异数量"], rows)

    def _positions_table(self, positions: pd.DataFrame) -> str:
        if positions.empty:
            return "_没有记录持仓。_"
        rows = []
        for row in positions.itertuples(index=False):
            rows.append(
                [
                    row.ts_code,
                    row.quantity,
                    row.available_quantity,
                    _money(row.avg_cost),
                    _money(row.market_value),
                    _percent(row.weight),
                ]
            )
        return _table(["代码", "数量", "可用数量", "平均成本", "市值", "权重"], rows)

    def _alpha_table(self, alpha_report: dict[str, Any]) -> str:
        summary = alpha_report.get("summary") if isinstance(alpha_report, dict) else None
        if not isinstance(summary, dict) or not summary:
            return "_没有记录 Alpha 研究摘要。_"
        rows = [
            ["因子", alpha_report.get("factor_name", "-")],
            ["持有期", alpha_report.get("horizon", "-")],
            ["分组数", alpha_report.get("quantiles", "-")],
            ["IC 均值", _decimal(summary.get("ic_mean"))],
            ["ICIR", _decimal(summary.get("icir"))],
            ["Rank IC 均值", _decimal(summary.get("rank_ic_mean"))],
            ["Rank ICIR", _decimal(summary.get("rank_icir"))],
            ["Rank IC 为正比例", _percent(summary.get("rank_ic_positive_rate"))],
            ["样本天数", _decimal(summary.get("sample_days"), digits=0)],
            ["最高组平均收益", _percent(summary.get("top_group_return_mean"))],
            ["最低组平均收益", _percent(summary.get("bottom_group_return_mean"))],
            ["多空平均收益", _percent(summary.get("long_short_return_mean"))],
            ["分组单调性", _percent(summary.get("group_monotonicity"))],
            ["最高分位换手率", _percent(summary.get("top_quantile_turnover_mean"))],
            ["样本外 Rank IC 均值", _decimal(summary.get("oos_rank_ic_mean"))],
            ["样本外 Rank ICIR", _decimal(summary.get("oos_rank_icir"))],
            ["样本外多空收益", _percent(summary.get("oos_long_short_return_mean"))],
            ["Rank IC 训练/测试差异", _decimal(summary.get("rank_ic_train_test_delta"))],
        ]
        return _table(["指标", "值"], rows)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"daily summary not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _data_source_note(summary: dict[str, Any]) -> str:
    mode = summary.get("market_data_mode")
    if isinstance(mode, dict):
        note = mode.get("note")
        label = mode.get("label")
        if note and label:
            return f"{label}。{note}"
        if note:
            return str(note)
    source = str(summary.get("data_source", "csv"))
    if source == "akshare":
        return "AkShare 真实 A 股行情，仅用于研究和模拟盘；当前系统尚未接入 QMT 实盘交易。"
    if source == "tushare":
        return "Tushare 行情数据，仅用于研究和模拟盘；当前系统尚未接入 QMT 实盘交易。"
    return "默认 `python -m quant.apps.start` / `daily` 使用本地样例数据或 CSV 数据，不代表真实行情或真实可交易标的。"


def _read_optional_json(path_value: object) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(str(path_value))
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _trade_date(summary: dict[str, Any]) -> str:
    value = summary.get("trade_date")
    if not value:
        raise ValueError("daily summary is missing trade_date")
    return pd.to_datetime(value).date().isoformat()


def _table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _cell(value: object) -> str:
    if value is None:
        return "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _money(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.2f}"


def _percent(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.2f}%"


def _decimal(value: object, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def _reconciliation_diff_count(detail: object) -> int:
    if isinstance(detail, list):
        return len(detail)
    if isinstance(detail, dict):
        order_differences = detail.get("order_differences", [])
        fill_differences = detail.get("fill_differences", [])
        count = 0
        if isinstance(order_differences, list):
            count += len(order_differences)
        if isinstance(fill_differences, list):
            count += len(fill_differences)
        return count
    return 0


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif _is_table_start(lines, index):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            html_lines.append(_table_to_html(table_lines))
            continue
        elif line.startswith("_") and line.endswith("_"):
            html_lines.append(f"<p><em>{html.escape(line.strip('_'))}</em></p>")
        else:
            html_lines.append(f"<p>{html.escape(line)}</p>")
        index += 1
    body = "\n".join(html_lines)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>每日量化报告</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; margin: 32px; color: #1f2937; }}
    h1, h2 {{ color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    p {{ line-height: 1.5; }}
    blockquote {{ margin: 12px 0 24px; padding: 12px 14px; border-left: 4px solid #b42318; background: #fff1f0; color: #7a271a; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def _is_table_start(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and lines[index].startswith("|")
        and lines[index + 1].startswith("|")
        and "---" in lines[index + 1]
    )


def _table_to_html(table_lines: list[str]) -> str:
    rows = [_split_table_row(line) for line in table_lines]
    headers = rows[0]
    body_rows = rows[2:]
    head = "".join(f"<th>{html.escape(cell)}</th>" for cell in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in body_rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _split_table_row(line: str) -> list[str]:
    return [cell.strip().replace("\\|", "|") for cell in line.strip().strip("|").split("|")]
