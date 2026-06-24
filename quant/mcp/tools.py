"""MCP 工具定义 - 调用现有 core 模块暴露量化能力。

工具分组：
  数据层：get_market_data, get_stock_info, get_benchmark_data, list_universe
  因子层：compute_factor, validate_alpha, list_factors
  策略层：list_strategies, get_strategy_info
  回测层：run_backtest, get_backtest_result, compare_backtest
  组合层：get_positions, get_portfolio_snapshot, get_risk_status
  系统层：get_system_status, get_daily_report, run_daily_workflow
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .security import (
    assert_code_size,
    assert_date_string,
    assert_positive_int,
    log_audit,
    redact_secrets,
)

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "research_store" / "reports"
DB_PATH = ROOT / "research_store" / "market_data.sqlite3"
PAPER_DB_PATH = ROOT / "research_store" / "paper_trading.sqlite3"


# ───────────────────────────── 数据层工具 ─────────────────────────────


def get_market_data(
    ts_code: str,
    start_date: str = "",
    end_date: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """获取股票日线数据。

    Args:
        ts_code: 股票代码，如 000001.SZ
        start_date: 开始日期（YYYY-MM-DD），默认最近 N 条
        end_date: 结束日期（YYYY-MM-DD）
        limit: 返回条数限制，默认 100
    """
    import sqlite3

    limit = assert_positive_int("limit", limit, default=100, max_value=2000)
    if start_date:
        start_date = assert_date_string("start_date", start_date)
    if end_date:
        end_date = assert_date_string("end_date", end_date)

    if not DB_PATH.exists():
        return {"error": True, "message": "数据库不存在，请先采集数据"}

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM daily_bar WHERE ts_code = ?"
        params: list[Any] = [ts_code]

        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)

        query += " ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        data = [dict(row) for row in rows]

        log_audit("get_market_data", {"ts_code": ts_code, "limit": limit})
        return {
            "ts_code": ts_code,
            "count": len(data),
            "data": data,
        }
    finally:
        conn.close()


def get_stock_info(ts_code: str = "") -> dict[str, Any]:
    """获取股票基本信息。

    Args:
        ts_code: 股票代码，为空则返回所有股票
    """
    import sqlite3

    if not DB_PATH.exists():
        return {"error": True, "message": "数据库不存在"}

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        if ts_code:
            rows = conn.execute(
                "SELECT * FROM stocks WHERE ts_code = ?", (ts_code,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM stocks LIMIT 100").fetchall()

        data = [dict(row) for row in rows]
        log_audit("get_stock_info", {"ts_code": ts_code})
        return {"count": len(data), "data": data}
    finally:
        conn.close()


def get_benchmark_data(
    benchmark_code: str = "000300.SH",
    start_date: str = "",
    end_date: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """获取基准指数数据。

    Args:
        benchmark_code: 基准代码，默认沪深300
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回条数
    """
    import sqlite3

    limit = assert_positive_int("limit", limit, default=100, max_value=2000)

    if not DB_PATH.exists():
        return {"error": True, "message": "数据库不存在"}

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM benchmark_bar WHERE benchmark_code = ?"
        params: list[Any] = [benchmark_code]

        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)

        query += " ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        data = [dict(row) for row in rows]

        log_audit("get_benchmark_data", {"benchmark_code": benchmark_code})
        return {"benchmark_code": benchmark_code, "count": len(data), "data": data}
    finally:
        conn.close()


def list_universe(min_amount: float = 50_000_000) -> dict[str, Any]:
    """查看当前股票池（通过流动性筛选）。

    Args:
        min_amount: 最小日均成交额，默认 5000 万
    """
    import sqlite3

    if not DB_PATH.exists():
        return {"error": True, "message": "数据库不存在"}

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        # 计算每只股票的 20 日平均成交额
        query = """
            SELECT ts_code, COUNT(*) as bar_count,
                   AVG(amount) as avg_amount
            FROM daily_bar
            WHERE trade_date >= date('now', '-30 days')
            GROUP BY ts_code
            HAVING avg_amount >= ?
            ORDER BY avg_amount DESC
        """
        rows = conn.execute(query, (min_amount,)).fetchall()
        data = [dict(row) for row in rows]

        log_audit("list_universe", {"min_amount": min_amount})
        return {"count": len(data), "min_amount": min_amount, "data": data}
    finally:
        conn.close()


# ───────────────────────────── 因子层工具 ─────────────────────────────


def list_factors() -> dict[str, Any]:
    """列出可用因子。"""
    from quant.core.factor.technical import (
        MomentumFactor,
        MovingAverageFactor,
        VolatilityFactor,
    )
    from quant.core.factor.quality import QualityScoreFactor

    factors = [
        {"name": "momentum_Nd", "class": "MomentumFactor", "params": {"window": "int"}},
        {"name": "volatility_Nd", "class": "VolatilityFactor", "params": {"window": "int"}},
        {"name": "ma_Nd", "class": "MovingAverageFactor", "params": {"window": "int"}},
        {"name": "quality_score", "class": "QualityScoreFactor", "params": {"window": 60}},
    ]

    log_audit("list_factors")
    return {"count": len(factors), "data": factors}


def compute_factor(
    factor_name: str,
    window: int = 20,
    start_date: str = "",
    end_date: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """计算指定因子值。

    Args:
        factor_name: 因子名称（momentum, volatility, quality）
        window: 因子窗口，默认 20
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回股票数
    """
    from quant.core.persistence.sqlite_store import SqliteStore
    from quant.core.factor.technical import MomentumFactor, VolatilityFactor
    from quant.core.factor.quality import QualityScoreFactor

    window = assert_positive_int("window", window, default=20, max_value=250)
    limit = assert_positive_int("limit", limit, default=10, max_value=100)

    store = SqliteStore(DB_PATH)
    bars = store.load_daily_bars(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )

    if bars.empty:
        return {"error": True, "message": "无数据"}

    # 选择因子
    if factor_name == "momentum":
        factor = MomentumFactor(window=window)
    elif factor_name == "volatility":
        factor = VolatilityFactor(window=window)
    elif factor_name == "quality":
        factor = QualityScoreFactor(window=window)
    else:
        return {"error": True, "message": f"未知因子: {factor_name}"}

    # 计算因子
    result = factor.calculate(bars)
    latest_date = result["trade_date"].max()
    latest = result[result["trade_date"] == latest_date].nlargest(limit, factor.name)

    data = latest[["ts_code", factor.name]].to_dict("records")

    log_audit("compute_factor", {"factor_name": factor_name, "window": window})
    return {
        "factor_name": factor_name,
        "window": window,
        "date": str(latest_date),
        "count": len(data),
        "data": data,
    }


def validate_alpha(
    factor_name: str,
    window: int = 20,
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    """Alpha 有效性验证 - 计算因子 IC 和分组收益。

    Args:
        factor_name: 因子名称
        window: 因子窗口
        start_date: 开始日期
        end_date: 结束日期
    """
    from quant.core.persistence.sqlite_store import SqliteStore
    from quant.core.factor.technical import MomentumFactor, VolatilityFactor
    from quant.core.factor.quality import QualityScoreFactor
    import pandas as pd

    store = SqliteStore(DB_PATH)
    bars = store.load_daily_bars(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )

    if bars.empty:
        return {"error": True, "message": "无数据"}

    # 选择因子
    if factor_name == "momentum":
        factor = MomentumFactor(window=window)
    elif factor_name == "volatility":
        factor = VolatilityFactor(window=window)
    elif factor_name == "quality":
        factor = QualityScoreFactor(window=window)
    else:
        return {"error": True, "message": f"未知因子: {factor_name}"}

    # 计算因子
    factor_df = factor.calculate(bars)

    # 计算未来收益
    close = bars.pivot(index="trade_date", columns="ts_code", values="close")
    future_ret = close.pct_change(periods=5).shift(-5)  # 5 日未来收益

    # 计算 IC（截面相关系数）
    ic_list = []
    for trade_date in factor_df["trade_date"].unique():
        f = factor_df[factor_df["trade_date"] == trade_date].set_index("ts_code")[factor.name]
        r = future_ret.loc[trade_date] if trade_date in future_ret.index else None
        if r is not None:
            merged = pd.DataFrame({"factor": f, "ret": r}).dropna()
            if len(merged) > 10:
                ic = merged["factor"].corr(merged["ret"])
                ic_list.append({"date": str(trade_date), "ic": round(float(ic), 4)})

    avg_ic = sum(item["ic"] for item in ic_list) / len(ic_list) if ic_list else 0
    ic_ir = avg_ic / (sum((item["ic"] - avg_ic) ** 2 for item in ic_list) / len(ic_list)) ** 0.5 if len(ic_list) > 1 else 0

    log_audit("validate_alpha", {"factor_name": factor_name, "window": window})
    return {
        "factor_name": factor_name,
        "window": window,
        "ic_count": len(ic_list),
        "avg_ic": round(avg_ic, 4),
        "ic_ir": round(ic_ir, 4),
        "ic_series": ic_list[-20:],  # 最近 20 个
        "interpretation": _interpret_ic(avg_ic, ic_ir),
    }


# ───────────────────────────── 策略层工具 ─────────────────────────────


def list_strategies() -> dict[str, Any]:
    """列出已注册策略。"""
    from quant.core.strategy.factory import build_strategy

    strategies = [
        {
            "id": "momentum_rank",
            "name": "动量排名策略",
            "factors": ["momentum_Nd"],
            "params": {"factor_name": "momentum_60d", "top_pct": 0.1, "max_holdings": 20},
        },
        {
            "id": "quality_rank",
            "name": "质量排名策略",
            "factors": ["quality_score"],
            "params": {"top_pct": 0.1, "max_holdings": 20},
        },
        {
            "id": "momentum_rank_trend",
            "name": "动量+趋势过滤",
            "factors": ["momentum_Nd", "trend"],
            "params": {"factor_name": "momentum_60d", "top_pct": 0.1, "max_holdings": 20},
        },
        {
            "id": "quality_rank_trend",
            "name": "质量+趋势过滤",
            "factors": ["quality_score", "trend"],
            "params": {"top_pct": 0.1, "max_holdings": 20},
        },
    ]

    log_audit("list_strategies")
    return {"count": len(strategies), "data": strategies}


def get_strategy_info(strategy_id: str) -> dict[str, Any]:
    """查看策略详情。

    Args:
        strategy_id: 策略 ID（momentum_rank, quality_rank 等）
    """
    from quant.core.strategy.factory import build_strategy

    try:
        strategy = build_strategy(strategy_id)
    except ValueError as e:
        return {"error": True, "message": str(e)}

    info = {
        "strategy_id": strategy.strategy_id,
        "strategy_version": strategy.strategy_version,
        "required_factors": [f.name for f in strategy.required_factors()],
        "parameters": {k: v for k, v in vars(strategy).items() if not k.startswith("_")},
    }

    log_audit("get_strategy_info", {"strategy_id": strategy_id})
    return info


# ───────────────────────────── 回测层工具 ─────────────────────────────


def run_backtest(
    strategy_id: str = "momentum_rank",
    start_date: str = "2025-01-01",
    end_date: str = "",
    rebalance: str = "weekly",
    initial_cash: float = 1_000_000,
    benchmark_code: str = "000300.SH",
) -> dict[str, Any]:
    """运行回测任务。

    Args:
        strategy_id: 策略 ID
        start_date: 开始日期
        end_date: 结束日期
        rebalance: 再平衡频率（weekly/monthly）
        initial_cash: 初始资金
        benchmark_code: 基准代码
    """
    from quant.core.persistence.sqlite_store import SqliteStore
    from quant.core.backtest.engine import BacktestEngine, BacktestRequest
    from quant.core.strategy.factory import build_strategy
    from quant.core.factor.technical import FactorEngine, MomentumFactor
    from quant.core.factor.quality import QualityScoreFactor

    start_date = assert_date_string("start_date", start_date)
    if not end_date:
        end_date = date.today().isoformat()
    end_date = assert_date_string("end_date", end_date)

    store = SqliteStore(DB_PATH)
    bars = store.load_daily_bars(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )
    stocks = store.load_stocks()
    benchmark_bars = store.load_benchmark_bars(benchmark_code)

    if bars.empty:
        return {"error": True, "message": "无数据"}

    # 构建策略
    strategy = build_strategy(strategy_id)

    # 构建因子引擎
    factors = strategy.required_factors()
    factor_engine = FactorEngine(factors) if factors else FactorEngine([MomentumFactor(60)])

    # 运行回测
    engine = BacktestEngine(factor_engine=factor_engine)
    result = engine.run(BacktestRequest(
        bars=bars,
        stocks=stocks,
        strategy=strategy,
        benchmark_bars=benchmark_bars,
        benchmark_code=benchmark_code,
        initial_cash=initial_cash,
        rebalance=rebalance,
    ))

    # 构建返回结果
    metrics = result.metrics
    equity_curve = [
        {"date": str(s.trade_date), "equity": round(s.total_asset, 2)}
        for s in result.snapshots[:50]  # 最近 50 个点
    ]

    log_audit("run_backtest", {
        "strategy_id": strategy_id,
        "start_date": start_date,
        "end_date": end_date,
    })

    return {
        "strategy_id": strategy_id,
        "period": f"{start_date} ~ {end_date}",
        "metrics": {
            "total_return": round(metrics.get("total_return", 0) * 100, 2),
            "annual_return": round(metrics.get("annual_return", 0) * 100, 2),
            "max_drawdown": round(metrics.get("max_drawdown", 0) * 100, 2),
            "sharpe": round(metrics.get("sharpe", 0), 4),
            "excess_return": round(metrics.get("excess_return", 0) * 100, 2),
            "benchmark_return": round(metrics.get("benchmark_total_return", 0) * 100, 2),
        },
        "equity_curve": equity_curve,
    }


def get_backtest_result() -> dict[str, Any]:
    """获取最新回测结果。"""
    for filename in ["akshare_backtest.json", "backtest.json"]:
        filepath = REPORTS_DIR / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            log_audit("get_backtest_result")
            return redact_secrets(data)

    return {"error": True, "message": "无回测结果"}


def compare_backtest(
    strategy_a: str = "momentum_rank",
    strategy_b: str = "quality_rank",
    start_date: str = "2025-01-01",
    end_date: str = "",
) -> dict[str, Any]:
    """对比两个策略的回测结果。

    Args:
        strategy_a: 策略 A ID
        strategy_b: 策略 B ID
        start_date: 开始日期
        end_date: 结束日期
    """
    result_a = run_backtest(strategy_id=strategy_a, start_date=start_date, end_date=end_date)
    result_b = run_backtest(strategy_id=strategy_b, start_date=start_date, end_date=end_date)

    if "error" in result_a:
        return result_a
    if "error" in result_b:
        return result_b

    log_audit("compare_backtest", {"a": strategy_a, "b": strategy_b})
    return {
        "strategy_a": result_a,
        "strategy_b": result_b,
        "winner": strategy_a if result_a["metrics"]["sharpe"] > result_b["metrics"]["sharpe"] else strategy_b,
    }


# ───────────────────────────── 组合层工具 ─────────────────────────────


def get_positions() -> dict[str, Any]:
    """查看当前持仓。"""
    import sqlite3

    if not PAPER_DB_PATH.exists():
        return {"error": True, "message": "模拟盘数据库不存在"}

    conn = sqlite3.connect(str(PAPER_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM positions WHERE quantity > 0"
        ).fetchall()
        data = [dict(row) for row in rows]

        log_audit("get_positions")
        return {"count": len(data), "data": data}
    finally:
        conn.close()


def get_portfolio_snapshot() -> dict[str, Any]:
    """查看组合快照。"""
    import sqlite3

    if not PAPER_DB_PATH.exists():
        return {"error": True, "message": "模拟盘数据库不存在"}

    conn = sqlite3.connect(str(PAPER_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM portfolio_snapshot ORDER BY trade_date DESC LIMIT 30"
        ).fetchall()
        data = [dict(row) for row in rows]

        log_audit("get_portfolio_snapshot")
        return {"count": len(data), "data": data}
    finally:
        conn.close()


def get_risk_status() -> dict[str, Any]:
    """查看风控状态。"""
    import sqlite3

    if not PAPER_DB_PATH.exists():
        return {"error": True, "message": "模拟盘数据库不存在"}

    conn = sqlite3.connect(str(PAPER_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        # 获取最新快照
        snapshot = conn.execute(
            "SELECT * FROM portfolio_snapshot ORDER BY trade_date DESC LIMIT 1"
        ).fetchone()

        # 获取风控检查记录
        risk_checks = conn.execute(
            "SELECT * FROM order_risk_check ORDER BY rowid DESC LIMIT 10"
        ).fetchall()

        log_audit("get_risk_status")
        return {
            "snapshot": dict(snapshot) if snapshot else None,
            "recent_risk_checks": [dict(row) for row in risk_checks],
        }
    finally:
        conn.close()


# ───────────────────────────── 系统层工具 ─────────────────────────────


def get_system_status() -> dict[str, Any]:
    """系统健康状态。"""
    import sqlite3

    status = {
        "market_data_db": DB_PATH.exists(),
        "paper_trading_db": PAPER_DB_PATH.exists(),
        "reports_dir": REPORTS_DIR.exists(),
    }

    # 检查数据新鲜度
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        try:
            row = conn.execute("SELECT MAX(trade_date) FROM daily_bar").fetchone()
            status["latest_data_date"] = row[0] if row else None
        finally:
            conn.close()

    # 检查持仓
    if PAPER_DB_PATH.exists():
        conn = sqlite3.connect(str(PAPER_DB_PATH))
        try:
            row = conn.execute("SELECT COUNT(*) FROM positions WHERE quantity > 0").fetchone()
            status["position_count"] = row[0] if row else 0
        finally:
            conn.close()

    log_audit("get_system_status")
    return status


def get_daily_report() -> dict[str, Any]:
    """获取最新日报。"""
    report_path = REPORTS_DIR / "daily_report.json"
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log_audit("get_daily_report")
        return redact_secrets(data)

    return {"error": True, "message": "无日报"}


def run_daily_workflow() -> dict[str, Any]:
    """触发日常工作流（异步执行）。"""
    import subprocess
    import sys

    log_audit("run_daily_workflow", result="submitted")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "quant.apps.start", "daily"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(ROOT),
        )
        return {
            "status": "submitted",
            "pid": proc.pid,
            "message": "日常工作流已提交，请通过 tasks 工具查看进度",
        }
    except Exception as e:
        return {"error": True, "message": str(e)}


# ───────────────────────────── 辅助函数 ─────────────────────────────


def _parse_date(value: str) -> date | None:
    """解析日期字符串。"""
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _interpret_ic(avg_ic: float, ic_ir: float) -> str:
    """解读 IC 值。"""
    if abs(avg_ic) < 0.02:
        return "因子无效（IC 接近 0）"
    elif abs(avg_ic) < 0.05:
        return "因子弱有效"
    elif abs(avg_ic) < 0.10:
        return "因子有效"
    else:
        return "因子强有效"

    if abs(ic_ir) > 0.5:
        return f"{interpretation}，稳定性好（IR={ic_ir:.2f}）"
    else:
        return f"{interpretation}，稳定性一般（IR={ic_ir:.2f}）"
