"""自定义脚本策略适配器 - 将脚本代码适配到 Strategy 接口。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from quant.core.factor.base import Factor
from quant.core.strategy.base import Strategy, StrategyContext


class ScriptStrategyAdapter(Strategy):
    """将自定义脚本适配到标准 Strategy 接口。

    用户编写 on_init/on_bar 函数，本适配器将其转换为 generate_signal 输出。
    """

    def __init__(self, script_code: str, strategy_id: str = "custom_script"):
        self._script_code = script_code
        self.strategy_id = strategy_id
        self.strategy_version = "v1"
        self._on_init = None
        self._on_bar = None
        self._compile_script()

    def _compile_script(self):
        """编译脚本代码。"""
        if not self._script_code or not self._script_code.strip():
            return

        # 安全执行环境
        exec_globals = {
            "__builtins__": {
                "abs": abs,
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
                "filter": filter,
                "float": float,
                "int": int,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "print": print,
                "range": range,
                "round": round,
                "set": set,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "zip": zip,
                # 数学函数
                "abs": abs,
            },
            "pd": pd,
        }
        exec_locals: dict[str, Any] = {}

        try:
            compiled = compile(self._script_code, "<strategy_script>", "exec")
            exec(compiled, exec_globals, exec_locals)
            self._on_init = exec_locals.get("on_init")
            self._on_bar = exec_locals.get("on_bar")
        except Exception as e:
            print(f"[ScriptStrategy] 编译脚本失败: {e}")

    def required_factors(self) -> list[Factor]:
        """脚本策略不需要预定义因子。"""
        return []

    def generate_signal(self, context: StrategyContext) -> pd.DataFrame:
        """生成信号 - 通过执行脚本实现。"""
        if not self._on_bar:
            # 如果没有 on_bar 函数，返回空信号
            return pd.DataFrame(columns=[
                "trade_date", "ts_code", "strategy_id", "strategy_version",
                "signal_type", "score", "reason",
            ])

        # 获取当日活跃股票
        active_codes = set(context.universe.loc[context.universe["is_active"], "ts_code"])

        # 获取当日价格数据
        today_bars = context.bars[
            (context.bars["trade_date"] == context.trade_date)
            & (context.bars["ts_code"].isin(active_codes))
        ]

        if today_bars.empty:
            return pd.DataFrame(columns=[
                "trade_date", "ts_code", "strategy_id", "strategy_version",
                "signal_type", "score", "reason",
            ])

        # 执行脚本，收集信号
        signals = []

        for _, bar_row in today_bars.iterrows():
            # 创建 Bar 对象
            from quant.core.strategy.script_runtime import Bar, ScriptContext, Position

            bar = Bar(
                ts_code=bar_row["ts_code"],
                trade_date=context.trade_date,
                open=float(bar_row.get("open", 0)),
                high=float(bar_row.get("high", 0)),
                low=float(bar_row.get("low", 0)),
                close=float(bar_row.get("close", 0)),
                volume=float(bar_row.get("volume", 0)),
                amount=float(bar_row.get("amount", 0)),
            )

            # 创建上下文
            ctx = ScriptContext(
                trade_date=context.trade_date,
                portfolio={},  # 简化：不维护持仓状态
                equity=1_000_000,
            )

            # 执行 on_bar
            try:
                self._on_bar(ctx, bar)

                # 收集订单信号
                for order in ctx._orders:
                    side = order.get("side", "BUY")
                    signals.append({
                        "trade_date": context.trade_date,
                        "ts_code": order.get("ts_code", bar.ts_code),
                        "strategy_id": self.strategy_id,
                        "strategy_version": self.strategy_version,
                        "signal_type": side,
                        "score": order.get("weight", 0.05),
                        "reason": f"script_signal_{side.lower()}",
                    })
            except Exception as e:
                print(f"[ScriptStrategy] 执行脚本失败 {bar.ts_code}: {e}")
                continue

        if not signals:
            return pd.DataFrame(columns=[
                "trade_date", "ts_code", "strategy_id", "strategy_version",
                "signal_type", "score", "reason",
            ])

        return pd.DataFrame(signals)


def load_script_from_db(experiment_id: str) -> str | None:
    """从数据库加载实验的脚本代码。"""
    import sqlite3
    from pathlib import Path

    db_path = Path("research_store/experiments.sqlite3")
    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT param_grid FROM experiments WHERE experiment_id = ?",
            (experiment_id,)
        )
        row = cursor.fetchone()
        if row and row[0]:
            import json
            param_grid = json.loads(row[0])
            return param_grid.get("code")
    except Exception as e:
        print(f"[ScriptStrategy] 加载脚本失败: {e}")
    finally:
        conn.close()

    return None


def create_custom_strategy(script_code: str, strategy_id: str = "custom_script") -> ScriptStrategyAdapter:
    """创建自定义脚本策略实例。"""
    return ScriptStrategyAdapter(script_code, strategy_id)
