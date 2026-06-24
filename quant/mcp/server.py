"""Stock Quant MCP Server - FastMCP 入口。

暴露量化系统能力为 MCP 工具，让 Claude Code 可以直接调用。

工具列表：
  数据层：get_market_data, get_stock_info, get_benchmark_data, list_universe
  因子层：compute_factor, validate_alpha, list_factors
  策略层：list_strategies, get_strategy_info
  回测层：run_backtest, get_backtest_result, compare_backtest
  组合层：get_positions, get_portfolio_snapshot, get_risk_status
  系统层：get_system_status, get_daily_report, run_daily_workflow
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .tools import (
    compare_backtest,
    compute_factor,
    get_backtest_result,
    get_benchmark_data,
    get_daily_report,
    get_market_data,
    get_portfolio_snapshot,
    get_positions,
    get_risk_status,
    get_stock_info,
    get_strategy_info,
    get_system_status,
    list_factors,
    list_strategies,
    list_universe,
    run_backtest,
    run_daily_workflow,
    validate_alpha,
)
from .security import log_audit

# 创建 MCP Server
mcp = FastMCP(
    "stock-quant",
    instructions=(
        "Stock Quant 量化研究系统 MCP 工具。"
        "可用于：查询股票数据、计算因子、运行回测、查看持仓、系统状态等。"
        "安全约束：只暴露查询和回测能力，不暴露交易执行。"
    ),
)


# ───────────────────────────── 注册工具 ─────────────────────────────


@mcp.tool()
def mcp_get_market_data(
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
    return get_market_data(ts_code, start_date, end_date, limit)


@mcp.tool()
def mcp_get_stock_info(ts_code: str = "") -> dict[str, Any]:
    """获取股票基本信息。

    Args:
        ts_code: 股票代码，为空则返回所有股票
    """
    return get_stock_info(ts_code)


@mcp.tool()
def mcp_get_benchmark_data(
    benchmark_code: str = "000300.SH",
    start_date: str = "",
    end_date: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """获取基准指数数据（如沪深300）。

    Args:
        benchmark_code: 基准代码，默认沪深300
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回条数
    """
    return get_benchmark_data(benchmark_code, start_date, end_date, limit)


@mcp.tool()
def mcp_list_universe(min_amount: float = 50_000_000) -> dict[str, Any]:
    """查看当前股票池（通过流动性筛选）。

    Args:
        min_amount: 最小日均成交额，默认 5000 万
    """
    return list_universe(min_amount)


@mcp.tool()
def mcp_list_factors() -> dict[str, Any]:
    """列出可用因子（动量、波动率、质量等）。"""
    return list_factors()


@mcp.tool()
def mcp_compute_factor(
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
    return compute_factor(factor_name, window, start_date, end_date, limit)


@mcp.tool()
def mcp_validate_alpha(
    factor_name: str,
    window: int = 20,
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    """Alpha 有效性验证 - 计算因子 IC 和分组收益。

    Args:
        factor_name: 因子名称（momentum, volatility, quality）
        window: 因子窗口
        start_date: 开始日期
        end_date: 结束日期
    """
    return validate_alpha(factor_name, window, start_date, end_date)


@mcp.tool()
def mcp_list_strategies() -> dict[str, Any]:
    """列出已注册策略（动量、质量、趋势过滤等）。"""
    return list_strategies()


@mcp.tool()
def mcp_get_strategy_info(strategy_id: str) -> dict[str, Any]:
    """查看策略详情。

    Args:
        strategy_id: 策略 ID（momentum_rank, quality_rank 等）
    """
    return get_strategy_info(strategy_id)


@mcp.tool()
def mcp_run_backtest(
    strategy_id: str = "momentum_rank",
    start_date: str = "2025-01-01",
    end_date: str = "",
    rebalance: str = "weekly",
    initial_cash: float = 1_000_000,
    benchmark_code: str = "000300.SH",
) -> dict[str, Any]:
    """运行回测任务。

    Args:
        strategy_id: 策略 ID（momentum_rank, quality_rank 等）
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD），默认今天
        rebalance: 再平衡频率（weekly/monthly）
        initial_cash: 初始资金，默认 100 万
        benchmark_code: 基准代码，默认沪深300
    """
    return run_backtest(strategy_id, start_date, end_date, rebalance, initial_cash, benchmark_code)


@mcp.tool()
def mcp_get_backtest_result() -> dict[str, Any]:
    """获取最新回测结果。"""
    return get_backtest_result()


@mcp.tool()
def mcp_compare_backtest(
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
    return compare_backtest(strategy_a, strategy_b, start_date, end_date)


@mcp.tool()
def mcp_get_positions() -> dict[str, Any]:
    """查看当前持仓。"""
    return get_positions()


@mcp.tool()
def mcp_get_portfolio_snapshot() -> dict[str, Any]:
    """查看组合快照（最近 30 天）。"""
    return get_portfolio_snapshot()


@mcp.tool()
def mcp_get_risk_status() -> dict[str, Any]:
    """查看风控状态。"""
    return get_risk_status()


@mcp.tool()
def mcp_get_system_status() -> dict[str, Any]:
    """系统健康状态（数据库、数据新鲜度等）。"""
    return get_system_status()


@mcp.tool()
def mcp_get_daily_report() -> dict[str, Any]:
    """获取最新日报。"""
    return get_daily_report()


@mcp.tool()
def mcp_run_daily_workflow() -> dict[str, Any]:
    """触发日常工作流（数据采集、信号生成、模拟交易）。"""
    return run_daily_workflow()


# ───────────────────────────── 入口 ─────────────────────────────


def main() -> None:
    """MCP Server 入口。"""
    parser = argparse.ArgumentParser(description="Stock Quant MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="传输模式（默认 stdio）",
    )
    args = parser.parse_args()

    log_audit("mcp_server_start", {"transport": args.transport})
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
