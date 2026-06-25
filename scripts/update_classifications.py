"""更新股票分类信息。"""
from __future__ import annotations

import sqlite3

import akshare as ak


def main():
    print("获取指数成分股...")

    # 获取所有指数成分股
    indices = {
        'CSI300': '000300',
        'CSI500': '000905',
        'CSI1000': '000852',
        'STAR50': '000688',
        'ChiNext': '399006',
        'SSE50': '000016',
    }

    index_stocks = {}
    for name, code in indices.items():
        try:
            df = ak.index_stock_cons(symbol=code)
            index_stocks[name] = set(df['品种代码'].tolist())
            print(f"  {name}: {len(index_stocks[name])} 只")
        except Exception as e:
            print(f"  {name}: 获取失败 - {e}")
            index_stocks[name] = set()

    print()
    print("更新数据库...")

    conn = sqlite3.connect('research_store/market_data.sqlite3')
    cursor = conn.cursor()

    # 更新分类
    updated = 0
    for row in cursor.execute('SELECT ts_code FROM stocks'):
        ts_code = row[0]
        code = ts_code.split('.')[0]

        # 判断分类
        categories = []
        for name, codes in index_stocks.items():
            if code in codes:
                categories.append(name)

        if categories:
            industry = '+'.join(categories)
        else:
            industry = 'Other'

        cursor.execute('UPDATE stocks SET industry = ? WHERE ts_code = ?', (industry, ts_code))
        updated += 1

    conn.commit()

    # 统计结果
    print()
    print("=== 更新后分类统计 ===")
    for row in cursor.execute('SELECT industry, COUNT(*) FROM stocks GROUP BY industry ORDER BY COUNT(*) DESC'):
        print(f"  {row[0]}: {row[1]} 只")

    conn.close()
    print()
    print(f"更新完成: {updated} 只股票")


if __name__ == "__main__":
    main()
