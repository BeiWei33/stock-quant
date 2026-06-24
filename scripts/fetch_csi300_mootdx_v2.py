"""Fetch CSI 300 stock data using mootdx with INSERT OR REPLACE."""
from __future__ import annotations

import sqlite3
import time
from datetime import date
from pathlib import Path

import pandas as pd
from mootdx.quotes import Quotes

DB_PATH = Path("research_store/market_data.sqlite3")
START_DATE = "2020-01-01"
END_DATE = "2026-06-24"


def main() -> None:
    print("=" * 60)
    print("  沪深300成分股数据获取 (mootdx)")
    print("=" * 60)
    print()

    # 1. Get CSI 300 components
    print("[1/3] 获取沪深300成分股列表...")
    import akshare as ak
    try:
        cons_df = ak.index_stock_cons(symbol="000300")
        stocks = cons_df["品种代码"].tolist()
        print(f"  成分股数量: {len(stocks)}")
    except Exception as e:
        print(f"  获取失败: {e}")
        return

    # 2. Connect to mootdx
    print("\n[2/3] 连接 mootdx 数据源...")
    try:
        client = Quotes.factory(market="std")
        print("  连接成功!")
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    # 3. Fetch stock data
    print(f"\n[3/3] 获取股票日线数据 ({START_DATE} - {END_DATE})...")
    conn = sqlite3.connect(str(DB_PATH))

    success_count = 0
    fail_count = 0
    total_bars = 0

    for i, symbol in enumerate(stocks):
        try:
            # Determine market (0=SZ, 1=SH)
            if symbol.startswith("6"):
                market = 1  # Shanghai
                ts_code = f"{symbol}.SH"
            else:
                market = 0  # Shenzhen
                ts_code = f"{symbol}.SZ"

            # Fetch daily data (frequency=9 for daily)
            df = client.bars(symbol=symbol, frequency=9, offset=800)

            if df is None or df.empty:
                print(f"  [{i+1}/{len(stocks)}] {symbol}: 无数据")
                fail_count += 1
                continue

            # Transform to our schema
            # Fix: remove duplicate datetime column before reset_index
            if 'datetime' in df.columns:
                df = df.drop(columns=['datetime'])
            df = df.reset_index()
            df = df.rename(columns={
                "datetime": "trade_date",
                "open": "open",
                "close": "close",
                "high": "high",
                "low": "low",
                "volume": "volume",
                "amount": "amount",
            })

            df["ts_code"] = ts_code
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
            df["adj_type"] = "qfq"
            df["source"] = "mootdx"
            df["quality_flag"] = "NORMAL"

            # Filter date range
            df = df[(df["trade_date"] >= START_DATE) & (df["trade_date"] <= END_DATE)]

            if df.empty:
                print(f"  [{i+1}/{len(stocks)}] {symbol}: 范围内无数据")
                fail_count += 1
                continue

            # Select columns
            df = df[["ts_code", "trade_date", "adj_type", "open", "high", "low", "close", "volume", "amount", "source", "quality_flag"]]

            # Insert into database using INSERT OR REPLACE
            for _, row in df.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO daily_bar
                       (ts_code, trade_date, adj_type, open, high, low, close, volume, amount, source, quality_flag)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (row["ts_code"], row["trade_date"], row["adj_type"], row["open"], row["high"], row["low"], row["close"], row["volume"], row["amount"], row["source"], row["quality_flag"])
                )

            success_count += 1
            total_bars += len(df)

            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(stocks)}] 已完成 {success_count} 只, 共 {total_bars} 条")
                conn.commit()

            # Small delay
            time.sleep(0.1)

        except Exception as e:
            print(f"  [{i+1}/{len(stocks)}] {symbol}: 失败 - {e}")
            fail_count += 1
            time.sleep(0.5)

    conn.commit()

    # 4. Update stock master table
    print(f"\n[4/4] 更新股票主表...")
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
