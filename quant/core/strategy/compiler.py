"""策略编译器 - 将 UI 配置转换为可执行脚本代码。

支持的策略类型：
  - 动量策略（momentum）
  - 均线交叉策略（ma_cross）
  - RSI 策略（rsi）
  - 布林带策略（bollinger）
  - 自定义脚本（custom）
"""
from __future__ import annotations

from typing import Any


class StrategyCompiler:
    """策略编译器 - 将配置转换为 Python 脚本。"""

    def compile(self, config: dict[str, Any]) -> str:
        """编译策略配置为 Python 脚本。

        Args:
            config: 策略配置字典

        Returns:
            可执行的 Python 脚本代码
        """
        strategy_type = config.get("strategy_type", "custom")

        if strategy_type == "custom":
            return config.get("code", "")

        # 根据策略类型生成代码
        compiler_map = {
            "momentum": self._compile_momentum,
            "ma_cross": self._compile_ma_cross,
            "rsi": self._compile_rsi,
            "bollinger": self._compile_bollinger,
            "dual_ma": self._compile_dual_ma,
        }

        compiler = compiler_map.get(strategy_type)
        if not compiler:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        return compiler(config)

    def _compile_momentum(self, config: dict[str, Any]) -> str:
        """编译动量策略。"""
        lookback = config.get("lookback", 20)
        threshold = config.get("threshold", 0)
        position_size = config.get("position_size", 0.05)

        return f'''
def on_init(ctx):
    ctx.set_param("lookback", {lookback})
    ctx.set_param("threshold", {threshold})
    ctx.set_param("position_size", {position_size})
    ctx.set_param("prices", {{}})

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    lookback = ctx.param("lookback")
    if len(prices[bar.ts_code]) < lookback + 1:
        return

    # 计算动量
    current = prices[bar.ts_code][-1]
    past = prices[bar.ts_code][-(lookback + 1)]
    momentum = (current - past) / past

    threshold = ctx.param("threshold")
    position_size = ctx.param("position_size")

    # 买入条件：动量超过阈值且无持仓
    if momentum > threshold and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=position_size, reason=f"momentum={{momentum:.4f}}")

    # 卖出条件：动量转负且有持仓
    elif momentum < 0 and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason=f"momentum={{momentum:.4f}}")
'''

    def _compile_ma_cross(self, config: dict[str, Any]) -> str:
        """编译均线交叉策略。"""
        fast_period = config.get("fast_period", 5)
        slow_period = config.get("slow_period", 20)
        position_size = config.get("position_size", 0.05)

        return f'''
def on_init(ctx):
    ctx.set_param("fast_period", {fast_period})
    ctx.set_param("slow_period", {slow_period})
    ctx.set_param("position_size", {position_size})
    ctx.set_param("prices", {{}})

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    fast_period = ctx.param("fast_period")
    slow_period = ctx.param("slow_period")

    if len(prices[bar.ts_code]) < slow_period:
        return

    # 计算均线
    fast_ma = sum(prices[bar.ts_code][-fast_period:]) / fast_period
    slow_ma = sum(prices[bar.ts_code][-slow_period:]) / slow_period

    position_size = ctx.param("position_size")

    # 金叉买入
    if fast_ma > slow_ma and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=position_size, reason="golden_cross")

    # 死叉卖出
    elif fast_ma < slow_ma and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason="death_cross")
'''

    def _compile_rsi(self, config: dict[str, Any]) -> str:
        """编译 RSI 策略。"""
        period = config.get("period", 14)
        oversold = config.get("oversold", 30)
        overbought = config.get("overbought", 70)
        position_size = config.get("position_size", 0.05)

        return f'''
def on_init(ctx):
    ctx.set_param("period", {period})
    ctx.set_param("oversold", {oversold})
    ctx.set_param("overbought", {overbought})
    ctx.set_param("position_size", {position_size})
    ctx.set_param("prices", {{}})

def _calculate_rsi(prices, period):
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    period = ctx.param("period")
    rsi = _calculate_rsi(prices[bar.ts_code], period)
    if rsi is None:
        return

    oversold = ctx.param("oversold")
    overbought = ctx.param("overbought")
    position_size = ctx.param("position_size")

    # 超卖买入
    if rsi < oversold and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=position_size, reason=f"rsi_oversold={{rsi:.1f}}")

    # 超买卖出
    elif rsi > overbought and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason=f"rsi_overbought={{rsi:.1f}}")
'''

    def _compile_bollinger(self, config: dict[str, Any]) -> str:
        """编译布林带策略。"""
        period = config.get("period", 20)
        std_dev = config.get("std_dev", 2)
        position_size = config.get("position_size", 0.05)

        return f'''
import math

def on_init(ctx):
    ctx.set_param("period", {period})
    ctx.set_param("std_dev", {std_dev})
    ctx.set_param("position_size", {position_size})
    ctx.set_param("prices", {{}})

def _calculate_bollinger(prices, period, std_dev):
    if len(prices) < period:
        return None, None, None
    recent = prices[-period:]
    middle = sum(recent) / period
    variance = sum((p - middle) ** 2 for p in recent) / period
    std = math.sqrt(variance)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    period = ctx.param("period")
    std_dev = ctx.param("std_dev")
    upper, middle, lower = _calculate_bollinger(prices[bar.ts_code], period, std_dev)

    if upper is None:
        return

    position_size = ctx.param("position_size")

    # 跌破下轨买入
    if bar.close < lower and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=position_size, reason="bollinger_lower")

    # 突破上轨卖出
    elif bar.close > upper and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason="bollinger_upper")
'''

    def _compile_dual_ma(self, config: dict[str, Any]) -> str:
        """编译双均线策略（与 ma_cross 类似，但支持更多参数）。"""
        fast_period = config.get("fast_period", 5)
        slow_period = config.get("slow_period", 20)
        position_size = config.get("position_size", 0.05)
        stop_loss = config.get("stop_loss", 0)
        take_profit = config.get("take_profit", 0)

        return f'''
def on_init(ctx):
    ctx.set_param("fast_period", {fast_period})
    ctx.set_param("slow_period", {slow_period})
    ctx.set_param("position_size", {position_size})
    ctx.set_param("stop_loss", {stop_loss})
    ctx.set_param("take_profit", {take_profit})
    ctx.set_param("prices", {{}})
    ctx.set_param("entry_prices", {{}})

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    fast_period = ctx.param("fast_period")
    slow_period = ctx.param("slow_period")

    if len(prices[bar.ts_code]) < slow_period:
        return

    fast_ma = sum(prices[bar.ts_code][-fast_period:]) / fast_period
    slow_ma = sum(prices[bar.ts_code][-slow_period:]) / slow_period

    position_size = ctx.param("position_size")
    stop_loss = ctx.param("stop_loss")
    take_profit = ctx.param("take_profit")
    entry_prices = ctx.param("entry_prices")

    # 止损止盈检查
    if ctx.has_position(bar.ts_code):
        entry_price = entry_prices.get(bar.ts_code, 0)
        if entry_price > 0:
            pnl_pct = (bar.close - entry_price) / entry_price
            if stop_loss > 0 and pnl_pct < -stop_loss:
                ctx.sell(bar.ts_code, reason=f"stop_loss={{pnl_pct:.4f}}")
                return
            if take_profit > 0 and pnl_pct > take_profit:
                ctx.sell(bar.ts_code, reason=f"take_profit={{pnl_pct:.4f}}")
                return

    # 金叉买入
    if fast_ma > slow_ma and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=position_size, reason="golden_cross")
        entry_prices[bar.ts_code] = bar.close

    # 死叉卖出
    elif fast_ma < slow_ma and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason="death_cross")
        entry_prices.pop(bar.ts_code, None)
'''

    def get_supported_types(self) -> list[dict[str, Any]]:
        """获取支持的策略类型列表。"""
        return [
            {
                "type": "momentum",
                "name": "动量策略",
                "description": "基于价格动量选股",
                "params": [
                    {"name": "lookback", "type": "int", "default": 20, "description": "回看周期"},
                    {"name": "threshold", "type": "float", "default": 0, "description": "动量阈值"},
                    {"name": "position_size", "type": "float", "default": 0.05, "description": "仓位大小"},
                ],
            },
            {
                "type": "ma_cross",
                "name": "均线交叉策略",
                "description": "快慢均线金叉死叉",
                "params": [
                    {"name": "fast_period", "type": "int", "default": 5, "description": "快线周期"},
                    {"name": "slow_period", "type": "int", "default": 20, "description": "慢线周期"},
                    {"name": "position_size", "type": "float", "default": 0.05, "description": "仓位大小"},
                ],
            },
            {
                "type": "rsi",
                "name": "RSI 策略",
                "description": "基于 RSI 超买超卖",
                "params": [
                    {"name": "period", "type": "int", "default": 14, "description": "RSI 周期"},
                    {"name": "oversold", "type": "float", "default": 30, "description": "超卖阈值"},
                    {"name": "overbought", "type": "float", "default": 70, "description": "超买阈值"},
                    {"name": "position_size", "type": "float", "default": 0.05, "description": "仓位大小"},
                ],
            },
            {
                "type": "bollinger",
                "name": "布林带策略",
                "description": "基于布林带突破",
                "params": [
                    {"name": "period", "type": "int", "default": 20, "description": "周期"},
                    {"name": "std_dev", "type": "float", "default": 2, "description": "标准差倍数"},
                    {"name": "position_size", "type": "float", "default": 0.05, "description": "仓位大小"},
                ],
            },
            {
                "type": "dual_ma",
                "name": "双均线策略",
                "description": "双均线 + 止损止盈",
                "params": [
                    {"name": "fast_period", "type": "int", "default": 5, "description": "快线周期"},
                    {"name": "slow_period", "type": "int", "default": 20, "description": "慢线周期"},
                    {"name": "position_size", "type": "float", "default": 0.05, "description": "仓位大小"},
                    {"name": "stop_loss", "type": "float", "default": 0.05, "description": "止损比例"},
                    {"name": "take_profit", "type": "float", "default": 0.10, "description": "止盈比例"},
                ],
            },
            {
                "type": "custom",
                "name": "自定义脚本",
                "description": "用户自定义 Python 脚本",
                "params": [
                    {"name": "code", "type": "text", "default": "", "description": "Python 代码"},
                ],
            },
        ]
