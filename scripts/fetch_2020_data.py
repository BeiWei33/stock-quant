"""用 akshare 获取 2020 年数据。"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import akshare as ak
import pandas as pd

DB_PATH = Path("research_store/market_data.sqlite3")


def main():
    print("用 akshare 获取 2020 年数据...")
    print()

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # 获取现有股票列表
    cursor.execute("SELECT DISTINCT ts_code FROM daily_bar")
    stocks = [row[0] for row in cursor.fetchall()]
    print(f"现有股票: {len(stocks)} 只")

    # 筛选需要获取 2020 年数据的股票
    stocks_to_fetch = []
    for ts_code in stocks:
        cursor.execute("SELECT MIN(trade_date) FROM daily_bar WHERE ts_code = ?", (ts_code,))
        min_date = cursor.fetchone()[0]
        if min_date and min_date > "2020-01-01":
            stocks_to_fetch.append(ts_code)

    print(f"需要补充 2020 年数据: {len(stocks_to_fetch)} 只")
    print()

    if not stocks_to_fetch:
        print("所有股票已有完整数据")
        conn.close()
        return

    # 用 akshare 获取数据
    success = 0
    fail = 0

    for i, ts_code in enumerate(stocks_to_fetch[:10]):  # 先测试 10 只
        try:
            # 提取股票代码
            symbol = ts_code.split(".")[0]

            # 获取日线数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="20200101",
                end_date="20201231",
                adjust="qfq"
            )

            if df is not None and not df.empty:
                # 转换格式
                df = df.rename(columns={
                    "日期": "trade_date",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "volume",
                    "成交额": "amount",
                })

                df["ts_code"] = ts_code
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
                df["adj_type"] = "qfq"
                df["source"] = "akshare"
                df["quality_flag"] = "NORMAL"

                # 插入数据
                for _, row in df.iterrows():
                    conn.execute(
                        """INSERT OR REPLACE INTO daily_bar
                           (ts_code, trade_date, adj_type, open, high, low, close, volume, amount, source, quality_flag)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (row["ts_code"], row["trade_date"], row["adj_type"], row["open"], row["high"], row["low"], row["close"], row["volume"], row["amount"], row["source"], row["quality_flag"])
                    )

                success += 1
                print(f"  [{i+1}] {ts_code}: {len(df)} 条")
            else:
                fail += 1
                print(f"  [{i+1}] {ts_code}: 无数据")

            time.sleep(0.5)  # akshare 需要更长间隔

        except Exception as e:
            fail += 1
            print(f"  [{i+1}] {ts_code}: 失败 - {e}")
            time.sleep(1)

    conn.commit()
    conn.close()

    print()
    print(f"完成: 成功 {success}, 失败 {fail}")


if __name__ == "__main__":
    main()
