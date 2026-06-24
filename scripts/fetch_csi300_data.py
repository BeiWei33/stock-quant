"""Fetch CSI 300 stock data from 2020 to present."""
from __future__ import annotations

import sqlite3
import time
from datetime import date
from pathlib import Path

import akshare as ak
import pandas as pd

DB_PATH = Path("research_store/market_data.sqlite3")
START_DATE = "20200101"
END_DATE = "20260624"


def main() -> None:
    print("=" * 60)
    print("  沪深300成分股数据获取 (2020-2026)")
    print("=" * 60)
    print()

    # 1. Get CSI 300 components
    print("[1/3] 获取沪深300成分股列表...")
    try:
        cons_df = ak.index_stock_cons(symbol="000300")
        stocks = cons_df["品种代码"].tolist()
        print(f"  成分股数量: {len(stocks)}")
    except Exception as e:
        print(f"  获取失败: {e}")
        return

    # 2. Fetch stock data
    print(f"\n[2/3] 获取股票日线数据 ({START_DATE} - {END_DATE})...")
    conn = sqlite3.connect(str(DB_PATH))

    success_count = 0
    fail_count = 0
    total_bars = 0

    for i, symbol in enumerate(stocks):
        try:
            # Fetch data
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=START_DATE,
                end_date=END_DATE,
                adjust="qfq",
            )

            if df.empty:
                print(f"  [{i+1}/{len(stocks)}] {symbol}: 无数据")
                fail_count += 1
                continue

            # Transform to our schema
            df = df.rename(columns={
                "日期": "trade_date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
            })

            # Add ts_code (convert to .SZ/.SH format)
            if symbol.startswith("6"):
                ts_code = f"{symbol}.SH"
            else:
                ts_code = f"{symbol}.SZ"

            df["ts_code"] = ts_code
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
            df["adj_type"] = "qfq"
            df["source"] = "akshare"
            df["quality_flag"] = "NORMAL"

            # Select columns
            df = df[["ts_code", "trade_date", "adj_type", "open", "high", "low", "close", "volume", "amount", "source", "quality_flag"]]

            # Insert into database
            df.to_sql("daily_bar", conn, if_exists="append", index=False)

            success_count += 1
            total_bars += len(df)

            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(stocks)}] 已完成 {success_count} 只, 共 {total_bars} 条")

            # Rate limit
            time.sleep(0.3)

        except Exception as e:
            print(f"  [{i+1}/{len(stocks)}] {symbol}: 失败 - {e}")
            fail_count += 1
            time.sleep(1)

    conn.commit()

    # 3. Update stock master table
    print(f"\n[3/3] 更新股票主表...")
    for symbol in stocks:
        if symbol.startswith("6"):
            ts_code = f"{symbol}.SH"
            exchange = "SSE"
        else:
            ts_code = f"{symbol}.SZ"
            exchange = "SZSE"

        conn.execute(
            "INSERT OR REPLACE INTO stocks (ts_code, name, exchange, list_date, is_st, status) VALUES (?, ?, ?, ?, ?, ?)",
            (ts_code, symbol, exchange, "2020-01-01", 0, "active"),
        )

    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print(f"  完成!")
    print(f"  成功: {success_count} 只")
    print(f"  失败: {fail_count} 只")
    print(f"  总条数: {total_bars}")
    print("=" * 60)


if __name__ == "__main__":
    main()
