"""获取沪深300和中证500完整数据（2020-2026）。"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import akshare as ak
import pandas as pd
from mootdx.quotes import Quotes

DB_PATH = Path("research_store/market_data.sqlite3")
START_DATE = "2020-01-01"
END_DATE = "2026-06-25"


def init_db():
    """初始化数据库。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_bar (
            ts_code TEXT,
            trade_date TEXT,
            adj_type TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            amount REAL,
            source TEXT,
            quality_flag TEXT,
            created_at TEXT,
            updated_at TEXT,
            PRIMARY KEY (ts_code, trade_date, adj_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            ts_code TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT,
            list_date TEXT,
            is_st INTEGER,
            status TEXT,
            industry TEXT
        )
    """)
    conn.commit()
    return conn


def get_index_stocks(index_code: str) -> list[str]:
    """获取指数成分股。"""
    try:
        df = ak.index_stock_cons(symbol=index_code)
        stocks = df["品种代码"].tolist()
        print(f"  {index_code} 成分股: {len(stocks)} 只")
        return stocks
    except Exception as e:
        print(f"  获取 {index_code} 成分股失败: {e}")
        return []


def fetch_stock_data(client: Quotes, symbol: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """获取单只股票数据。"""
    try:
        # 获取日线数据
        df = client.bars(symbol=symbol, frequency=9, offset=800)

        if df is None or df.empty:
            return None

        # 转换格式
        if "datetime" in df.columns:
            df = df.drop(columns=["datetime"])
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

        # 确定市场代码
        if symbol.startswith("6"):
            ts_code = f"{symbol}.SH"
        else:
            ts_code = f"{symbol}.SZ"

        df["ts_code"] = ts_code
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
        df["adj_type"] = "qfq"
        df["source"] = "mootdx"
        df["quality_flag"] = "NORMAL"

        # 过滤日期范围
        df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]

        if df.empty:
            return None

        return df[["ts_code", "trade_date", "adj_type", "open", "high", "low", "close", "volume", "amount", "source", "quality_flag"]]

    except Exception as e:
        return None


def main():
    print("=" * 60)
    print("  沪深300 + 中证500 数据获取")
    print("=" * 60)
    print()

    # 1. 初始化数据库
    print("[1/5] 初始化数据库...")
    conn = init_db()

    # 2. 获取成分股列表
    print("[2/5] 获取指数成分股...")
    csi300_stocks = get_index_stocks("000300")
    csi500_stocks = get_index_stocks("000905")

    # 合并去重
    all_stocks = list(set(csi300_stocks + csi500_stocks))
    print(f"  总计: {len(all_stocks)} 只（去重后）")

    # 3. 连接 mootdx
    print("\n[3/5] 连接 mootdx 数据源...")
    try:
        client = Quotes.factory(market="std")
        print("  连接成功!")
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    # 4. 获取数据
    print(f"\n[4/5] 获取股票日线数据 ({START_DATE} - {END_DATE})...")

    # 检查已有数据
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ts_code FROM daily_bar")
    existing_stocks = set(row[0] for row in cursor.fetchall())
    print(f"  已有数据: {len(existing_stocks)} 只股票")

    # 筛选需要获取的股票
    stocks_to_fetch = []
    for symbol in all_stocks:
        if symbol.startswith("6"):
            ts_code = f"{symbol}.SH"
        else:
            ts_code = f"{symbol}.SZ"
        if ts_code not in existing_stocks:
            stocks_to_fetch.append(symbol)

    print(f"  需要获取: {len(stocks_to_fetch)} 只股票")

    success_count = 0
    fail_count = 0
    total_bars = 0

    for i, symbol in enumerate(stocks_to_fetch):
        try:
            df = fetch_stock_data(client, symbol, START_DATE, END_DATE)

            if df is not None and not df.empty:
                # 插入数据
                for _, row in df.iterrows():
                    conn.execute(
                        """INSERT OR REPLACE INTO daily_bar
                           (ts_code, trade_date, adj_type, open, high, low, close, volume, amount, source, quality_flag)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (row["ts_code"], row["trade_date"], row["adj_type"], row["open"], row["high"], row["low"], row["close"], row["volume"], row["amount"], row["source"], row["quality_flag"])
                    )

                success_count += 1
                total_bars += len(df)

                if (i + 1) % 20 == 0:
                    print(f"  [{i+1}/{len(stocks_to_fetch)}] 已完成 {success_count} 只, 共 {total_bars} 条")
                    conn.commit()
            else:
                fail_count += 1

            time.sleep(0.1)  # 避免请求过快

        except Exception as e:
            print(f"  [{i+1}] {symbol}: 失败 - {e}")
            fail_count += 1
            time.sleep(0.5)

    conn.commit()

    # 5. 更新股票主表
    print(f"\n[5/5] 更新股票主表...")

    # 标记沪深300和中证500
    csi300_set = set(csi300_stocks)
    csi500_set = set(csi500_stocks)

    for symbol in all_stocks:
        if symbol.startswith("6"):
            ts_code = f"{symbol}.SH"
            exchange = "SSE"
        else:
            ts_code = f"{symbol}.SZ"
            exchange = "SZSE"

        # 判断所属指数
        if symbol in csi300_set and symbol in csi500_set:
            industry = "CSI300+CSI500"
        elif symbol in csi300_set:
            industry = "CSI300"
        elif symbol in csi500_set:
            industry = "CSI500"
        else:
            industry = "Unknown"

        conn.execute(
            "INSERT OR REPLACE INTO stocks (ts_code, name, exchange, list_date, is_st, status, industry) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts_code, symbol, exchange, "2020-01-01", 0, "active", industry),
        )

    conn.commit()

    # 统计结果
    cursor.execute("SELECT COUNT(DISTINCT ts_code) FROM daily_bar")
    total_stocks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM daily_bar")
    total_records = cursor.fetchone()[0]

    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_bar")
    dates = cursor.fetchone()

    conn.close()

    print()
    print("=" * 60)
    print("  完成!")
    print("=" * 60)
    print(f"  成功获取: {success_count} 只")
    print(f"  获取失败: {fail_count} 只")
    print(f"  新增条数: {total_bars:,}")
    print()
    print(f"  数据库统计:")
    print(f"    总股票数: {total_stocks}")
    print(f"    总记录数: {total_records:,}")
    print(f"    时间范围: {dates[0]} 到 {dates[1]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
