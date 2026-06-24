# Stock Quant MCP Server

让 Claude Code 直接驱动量化流程的 MCP 工具集。

## 功能

### 数据层
- `get_market_data` - 获取股票日线数据
- `get_stock_info` - 获取股票基本信息
- `get_benchmark_data` - 获取基准指数数据（沪深300等）
- `list_universe` - 查看当前股票池

### 因子层
- `list_factors` - 列出可用因子
- `compute_factor` - 计算指定因子值
- `validate_alpha` - Alpha 有效性验证（IC 分析）

### 策略层
- `list_strategies` - 列出已注册策略
- `get_strategy_info` - 查看策略详情

### 回测层
- `run_backtest` - 运行回测任务
- `get_backtest_result` - 获取最新回测结果
- `compare_backtest` - 对比两个策略

### 组合层
- `get_positions` - 查看当前持仓
- `get_portfolio_snapshot` - 查看组合快照
- `get_risk_status` - 查看风控状态

### 系统层
- `get_system_status` - 系统健康状态
- `get_daily_report` - 获取日报
- `run_daily_workflow` - 触发日常工作流

## 安装

```bash
pip install mcp>=1.2.0
```

## 使用方法

### stdio 模式（默认）

```bash
python -m quant.mcp.server
```

### SSE 模式

```bash
python -m quant.mcp.server --transport sse
```

## Claude Code 配置

在 `.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "stock-quant": {
      "command": "python",
      "args": ["-m", "quant.mcp.server"],
      "cwd": "d:/Agent/codex/workspace/stock-quant"
    }
  }
}
```

## 安全约束

- 只暴露查询和回测能力，不暴露交易执行
- 所有工具调用写入审计日志
- 敏感信息自动脱敏
- 代码输入限制 50KB

## 示例对话

```
用户：帮我查一下平安银行最近的走势
Claude：调用 get_market_data(ts_code="000001.SZ", limit=30)

用户：跑一下动量策略的回测
Claude：调用 run_backtest(strategy_id="momentum_rank", start_date="2025-01-01")

用户：对比动量和质量策略
Claude：调用 compare_backtest(strategy_a="momentum_rank", strategy_b="quality_rank")
```
