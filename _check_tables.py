import sqlite3
conn = sqlite3.connect('D:/Agent/codex/workspace/stock-quant/research_store/paper_trading.sqlite3')
cu = conn.cursor()
cu.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('stocks','sqlite_sequence','benchmark_bar','daily_bar','strategy_registry') ORDER BY name")
tables = [r[0] for r in cu.fetchall()]
print('Tables to clear:', tables)
conn.close()