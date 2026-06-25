"""从 rustdx 导出的 CSV 导入数据到本地数据库。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

CSV_PATH = Path("D:/Agent/git/rustdx/target/release/a_stock_data.csv")
DB_PATH = Path("research_store/market_data.sqlite3")
START_DATE = "2020-01-01"


def main():
    print("=" * 60)
    print("  从 rustdx CSV 导入数据")
    print("=" * 60)
    print()

    # 初始化数据库
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

    # 获取现有股票
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ts_code FROM daily_bar")
    existing_stocks = set(row[0] for row in cursor.fetchall())
    print(f"数据库现有股票: {len(existing_stocks)} 只")

    # 读取 CSV（只读取 2020 年以后的数据）
    print(f"\n读取 CSV 文件 ({START_DATE} 以后的数据)...")
    print(f"文件: {CSV_PATH}")
    print("这可能需要几分钟...")

    # 分块读取
    chunks = pd.read_csv(
        CSV_PATH,
        chunksize=100000,
        dtype={
            "date": str,
            "code": str,
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "amount": float,
            "vol": float,
            "preclose": float,
            "factor": float,
        }
    )

    total_inserted = 0
    stocks_imported = set()

    for chunk_num, chunk in enumerate(chunks):
        # 过滤日期
        chunk = chunk[chunk["date"] >= START_DATE]

        if chunk.empty:
            continue

        # 转换格式
        for _, row in chunk.iterrows():
            code = row["code"]
            # 确定市场代码
            if code.startswith("6"):
                ts_code = f"{code}.SH"
                exchange = "SSE"
            elif code.startswith("0") or code.startswith("3"):
                ts_code = f"{code}.SZ"
                exchange = "SZSE"
            else:
                ts_code = f"{code}.BJ"
                exchange = "BJSE"

            # 只导入沪深股票（跳过北交所）
            if exchange == "BJSE":
                continue

            # 插入数据
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO daily_bar
                       (ts_code, trade_date, adj_type, open, high, low, close, volume, amount, source, quality_flag)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ts_code,
                        row["date"],
                        "qfq",  # 使用前复权
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                        int(row["vol"]),
                        row["amount"],
                        "rustdx",
                        "NORMAL",
                    )
                )
                total_inserted += 1
                stocks_imported.add(ts_code)
            except Exception as e:
                pass

        # 每 10 个 chunk 提交一次
        if (chunk_num + 1) % 10 == 0:
            conn.commit()
            print(f"  已处理 {(chunk_num + 1) * 100000:,} 行, 导入 {total_inserted:,} 条, {len(stocks_imported)} 只股票")

    conn.commit()

    # 更新股票主表
    print("\n更新股票主表...")
    for ts_code in stocks_imported:
        code = ts_code.split(".")[0]
        if ts_code.endswith(".SH"):
            exchange = "SSE"
        else:
            exchange = "SZSE"

        conn.execute(
            "INSERT OR IGNORE INTO stocks (ts_code, name, exchange, list_date, is_st, status, industry) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts_code, code, exchange, "2020-01-01", 0, "active", "Unknown"),
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
    print(f"  新导入股票: {len(stocks_imported)} 只")
    print(f"  新导入记录: {total_inserted:,} 条")
    print()
    print(f"  数据库统计:")
    print(f"    总股票数: {total_stocks}")
    print(f"    总记录数: {total_records:,}")
    print(f"    时间范围: {dates[0]} 到 {dates[1]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
