"""Script 策略运行时 - 事件驱动策略编写方式。

使用方法：
    class MyStrategy(ScriptStrategy):
        def on_init(self, ctx):
            self.lookback = 20
            self.ma = []

        def on_bar(self, ctx, bar):
            self.ma.append(bar.close)
            if len(self.ma) >= self.lookback:
                avg = sum(self.ma[-self.lookback:]) / self.lookback
                if bar.close > avg and not ctx.has_position(bar.ts_code):
                    ctx.buy(bar.ts_code, weight=0.05)
                elif bar.close < avg and ctx.has_position(bar.ts_code):
                    ctx.sell(bar.ts_code)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import pandas as pd


@dataclass
class Bar:
    """K 线数据。"""
    ts_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


@dataclass
class Position:
    """持仓信息。"""
    ts_code: str
    quantity: int
    avg_cost: float
    market_value: float
    weight: float


class ScriptContext:
    """策略运行时上下文。"""

    def __init__(self, trade_date: date, portfolio: dict[str, Position], equity: float):
        self.trade_date = trade_date
        self.portfolio = portfolio
        self.equity = equity
        self._orders: list[dict[str, Any]] = []
        self._logs: list[str] = []

    def buy(self, ts_code: str, weight: float = 0.05, quantity: int = 0):
        """买入股票。

        Args:
            ts_code: 股票代码
            weight: 目标仓位权重（0-1）
            quantity: 指定数量（优先于 weight）
        """
        self._orders.append({
            "ts_code": ts_code,
            "side": "BUY",
            "weight": weight,
            "quantity": quantity,
        })

    def sell(self, ts_code: str, weight: float = 0, quantity: int = 0):
        """卖出股票。

        Args:
            ts_code: 股票代码
            weight: 卖出权重（0 表示全部卖出）
            quantity: 指定数量（优先于 weight）
        """
        self._orders.append({
            "ts_code": ts_code,
            "side": "SELL",
            "weight": weight,
            "quantity": quantity,
        })

    def has_position(self, ts_code: str) -> bool:
        """检查是否持有某只股票。"""
        return ts_code in self.portfolio

    def get_position(self, ts_code: str) -> Position | None:
        """获取持仓信息。"""
        return self.portfolio.get(ts_code)

    def get_positions(self) -> dict[str, Position]:
        """获取所有持仓。"""
        return self.portfolio.copy()

    def log(self, message: str):
        """记录日志。"""
        self._logs.append(f"[{self.trade_date}] {message}")

    def get_orders(self) -> list[dict[str, Any]]:
        """获取所有订单。"""
        return self._orders.copy()

    def get_logs(self) -> list[str]:
        """获取所有日志。"""
        return self._logs.copy()


class ScriptStrategy:
    """事件驱动策略基类。"""

    def on_init(self, ctx: ScriptContext):
        """初始化，设置参数。"""
        pass

    def on_bar(self, ctx: ScriptContext, bar: Bar):
        """每根 K 线触发。"""
        pass

    def on_order_filled(self, ctx: ScriptContext, order: dict[str, Any]):
        """订单成交触发。"""
        pass

    def on_day_end(self, ctx: ScriptContext):
        """每日结束触发。"""
        pass


class ScriptStrategyAdapter:
    """将 ScriptStrategy 适配为标准 Strategy 接口。"""

    def __init__(self, script: ScriptStrategy):
        self.script = script
        self.strategy_id = script.__class__.__name__
        self.strategy_version = "v1"

    def required_factors(self) -> list:
        """Script 策略不需要预定义因子。"""
        return []

    def generate_signal(self, context) -> pd.DataFrame:
        """生成信号（适配标准接口）。"""
        # 这里需要将 Script 策略的输出转换为标准信号格式
        # 实际实现在 BacktestEngine 中
        return pd.DataFrame()


class ScriptBacktestEngine:
    """Script 策略回测引擎。"""

    def __init__(self):
        pass

    def run(
        self,
        script: ScriptStrategy,
        bars: pd.DataFrame,
        stocks: pd.DataFrame,
        initial_cash: float = 1_000_000,
        commission_rate: float = 0.0003,
    ) -> dict[str, Any]:
        """运行 Script 策略回测。

        Args:
            script: Script 策略实例
            bars: 日线数据
            stocks: 股票信息
            initial_cash: 初始资金
            commission_rate: 佣金率

        Returns:
            回测结果
        """
        # 准备数据
        dates = sorted(bars["trade_date"].unique())
        close_matrix = bars.pivot(index="trade_date", columns="ts_code", values="close")
        open_matrix = bars.pivot(index="trade_date", columns="ts_code", values="open")
        high_matrix = bars.pivot(index="trade_date", columns="ts_code", values="high")
        low_matrix = bars.pivot(index="trade_date", columns="ts_code", values="low")
        volume_matrix = bars.pivot(index="trade_date", columns="ts_code", values="volume")
        amount_matrix = bars.pivot(index="trade_date", columns="ts_code", values="amount")

        # 初始化
        cash = initial_cash
        portfolio: dict[str, Position] = {}
        equity_curve = []
        all_orders = []
        all_logs = []

        # 初始化策略
        init_ctx = ScriptContext(dates[0], portfolio, cash)
        script.on_init(init_ctx)
        all_logs.extend(init_ctx.get_logs())

        # 逐日回测
        for trade_date in dates:
            ctx = ScriptContext(trade_date, portfolio, cash)

            # 遍历每只股票
            for ts_code in close_matrix.columns:
                if pd.isna(close_matrix.loc[trade_date, ts_code]):
                    continue

                bar = Bar(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    open=float(open_matrix.loc[trade_date, ts_code]) if not pd.isna(open_matrix.loc[trade_date, ts_code]) else 0,
                    high=float(high_matrix.loc[trade_date, ts_code]) if not pd.isna(high_matrix.loc[trade_date, ts_code]) else 0,
                    low=float(low_matrix.loc[trade_date, ts_code]) if not pd.isna(low_matrix.loc[trade_date, ts_code]) else 0,
                    close=float(close_matrix.loc[trade_date, ts_code]),
                    volume=float(volume_matrix.loc[trade_date, ts_code]) if not pd.isna(volume_matrix.loc[trade_date, ts_code]) else 0,
                    amount=float(amount_matrix.loc[trade_date, ts_code]) if not pd.isna(amount_matrix.loc[trade_date, ts_code]) else 0,
                )

                script.on_bar(ctx, bar)

            # 处理订单
            orders = ctx.get_orders()
            for order in orders:
                self._execute_order(
                    order=order,
                    cash=cash,
                    portfolio=portfolio,
                    close_prices=close_matrix.loc[trade_date],
                    equity=cash + sum(p.market_value for p in portfolio.values()),
                    commission_rate=commission_rate,
                )
                all_orders.append({**order, "trade_date": trade_date})

            # 更新持仓市值
            for ts_code, pos in portfolio.items():
                if ts_code in close_matrix.columns:
                    price = close_matrix.loc[trade_date, ts_code]
                    if not pd.isna(price):
                        pos.market_value = pos.quantity * float(price)

            # 计算净值
            equity = cash + sum(p.market_value for p in portfolio.values())
            equity_curve.append({
                "trade_date": trade_date,
                "equity": equity,
                "cash": cash,
                "market_value": equity - cash,
            })

            # 日结束回调
            ctx = ScriptContext(trade_date, portfolio, cash)
            script.on_day_end(ctx)
            all_logs.extend(ctx.get_logs())

        # 计算指标
        equity_series = pd.Series([e["equity"] for e in equity_curve])
        returns = equity_series.pct_change().dropna()

        metrics = {
            "total_return": (equity_series.iloc[-1] / initial_cash - 1) if len(equity_series) > 0 else 0,
            "annual_return": self._annual_return(equity_series, len(dates)),
            "max_drawdown": self._max_drawdown(equity_series),
            "sharpe": self._sharpe(returns),
            "win_rate": self._win_rate(returns),
        }

        return {
            "metrics": metrics,
            "equity_curve": equity_curve,
            "orders": all_orders,
            "logs": all_logs,
        }

    def _execute_order(
        self,
        order: dict[str, Any],
        cash: float,
        portfolio: dict[str, Position],
        close_prices: pd.Series,
        equity: float,
        commission_rate: float,
    ):
        """执行订单。"""
        ts_code = order["ts_code"]
        side = order["side"]
        weight = order.get("weight", 0)
        quantity = order.get("quantity", 0)

        if ts_code not in close_prices or pd.isna(close_prices[ts_code]):
            return

        price = float(close_prices[ts_code])
        if price <= 0:
            return

        if side == "BUY":
            # 计算买入数量
            if quantity <= 0 and weight > 0:
                target_value = equity * weight
                quantity = int(target_value / price / 100) * 100  # 整百股

            if quantity <= 0:
                return

            # 计算成本
            amount = price * quantity
            commission = max(amount * commission_rate, 5)
            total_cost = amount + commission

            if total_cost > cash:
                return

            # 更新持仓
            if ts_code in portfolio:
                pos = portfolio[ts_code]
                total_quantity = pos.quantity + quantity
                total_cost_basis = pos.avg_cost * pos.quantity + price * quantity
                pos.avg_cost = total_cost_basis / total_quantity
                pos.quantity = total_quantity
            else:
                portfolio[ts_code] = Position(
                    ts_code=ts_code,
                    quantity=quantity,
                    avg_cost=price,
                    market_value=amount,
                    weight=weight,
                )

        elif side == "SELL":
            if ts_code not in portfolio:
                return

            pos = portfolio[ts_code]

            # 计算卖出数量
            if quantity <= 0:
                quantity = pos.quantity  # 全部卖出
            else:
                quantity = min(quantity, pos.quantity)

            if quantity <= 0:
                return

            # 计算收入
            amount = price * quantity
            commission = max(amount * commission_rate, 5)
            tax = amount * 0.001  # 印花税
            net_income = amount - commission - tax

            # 更新持仓
            pos.quantity -= quantity
            if pos.quantity <= 0:
                del portfolio[ts_code]

    def _annual_return(self, equity_series: pd.Series, trading_days: int) -> float:
        """计算年化收益。"""
        if len(equity_series) < 2 or trading_days < 1:
            return 0
        total_return = equity_series.iloc[-1] / equity_series.iloc[0] - 1
        years = trading_days / 252
        if years <= 0:
            return 0
        return (1 + total_return) ** (1 / years) - 1

    def _max_drawdown(self, equity_series: pd.Series) -> float:
        """计算最大回撤。"""
        if len(equity_series) < 2:
            return 0
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak
        return abs(drawdown.min())

    def _sharpe(self, returns: pd.Series, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率。"""
        if len(returns) < 2:
            return 0
        excess_returns = returns.mean() * 252 - risk_free_rate
        volatility = returns.std() * (252 ** 0.5)
        if volatility <= 0:
            return 0
        return excess_returns / volatility

    def _win_rate(self, returns: pd.Series) -> float:
        """计算胜率。"""
        if len(returns) < 1:
            return 0
        return (returns > 0).sum() / len(returns)
