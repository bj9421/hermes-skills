#!/usr/bin/env python3
"""
驗證 screen_cache 技術指標完整性：NULL 檢查、跨表比對、抽樣合理性。
無相依（只用 sqlite3），可直接用系統 python 執行。

Usage:
    python3 /opt/data/skills/taiwan-stock-data-pipeline/scripts/verify_tech_indicators.py
"""
import sqlite3
import sys
import os

DB_CANDIDATES = [
    os.environ.get("STOCK_DB_PATH"),
    "/opt/data/taiwan_stocks.db",
    os.path.join(os.path.dirname(__file__), "../../../taiwan_stocks.db"),
]
DB_PATH = next((p for p in DB_CANDIDATES if p and os.path.exists(p)), None)
if not DB_PATH:
    print("❌ 找不到 taiwan_stocks.db，請設定 STOCK_DB_PATH 環境變數")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

total = cur.execute("SELECT COUNT(*) FROM screen_cache").fetchone()[0]
print(f"📊 screen_cache 總筆數: {total}")

indicator_cols = [
    "rsi_6", "rsi_12", "rsi_14",
    "ma5", "ma10", "ma20", "ma60",
    "macd",
    "bollinger_upper", "bollinger_middle", "bollinger_lower", "bollinger_width",
    "volume_ratio", "volume_change",
    "price", "volume",
]
print(f"\n{'='*50}")
print("NULL 完整性檢查")
print(f"{'='*50}")
has_null = False
for col in indicator_cols:
    n = cur.execute(f"SELECT COUNT(*) FROM screen_cache WHERE {col} IS NULL").fetchone()[0]
    status = "✅" if n == 0 else "❌"
    if n > 0:
        has_null = True
    print(f"  {status} {col:25s}: {n:>5}" + (f" / {total}" if n > 0 else ""))

print(f"\n{'='*50}")
print("跨表比對 (daily_prices ↔ screen_cache)")
print(f"{'='*50}")
has_price = cur.execute("SELECT COUNT(DISTINCT stock_code) FROM daily_prices").fetchone()[0]
in_cache = cur.execute("SELECT COUNT(DISTINCT stock_code) FROM screen_cache").fetchone()[0]
only_price = cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT DISTINCT stock_code FROM daily_prices
        EXCEPT
        SELECT DISTINCT stock_code FROM screen_cache
    )
""").fetchone()[0]
only_cache = cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT DISTINCT stock_code FROM screen_cache
        EXCEPT
        SELECT DISTINCT stock_code FROM daily_prices
    )
""").fetchone()[0]
print(f"  daily_prices 有資料: {has_price}")
print(f"  screen_cache 有資料: {in_cache}")
print(f"  {'✅' if only_price == 0 else '❌'} daily_prices 有但 screen_cache 無: {only_price}")
print(f"  {'✅' if only_cache == 0 else '❌'} screen_cache 有但 daily_prices 無: {only_cache}")

samples = cur.execute(
    "SELECT volume_ratio FROM screen_cache WHERE volume_ratio IS NOT NULL ORDER BY RANDOM() LIMIT 10"
).fetchall()
vals = [round(r[0], 2) for r in samples]
print(f"\n  volume_ratio 抽樣: {vals}")
outliers = cur.execute(
    "SELECT COUNT(*) FROM screen_cache WHERE volume_ratio > 20 OR volume_ratio < 0"
).fetchone()[0]
print(f"  {'✅' if outliers == 0 else '⚠️'} 離群值 (volume_ratio > 20 或 < 0): {outliers}")

latest_row = cur.execute("SELECT MAX(cached_at) FROM screen_cache").fetchone()[0]
latest_price_date = cur.execute("SELECT MAX(date) FROM daily_prices").fetchone()[0]
print(f"\n{'='*50}")
print("資料新鮮度")
print(f"{'='*50}")
print(f"  screen_cache 最後更新: {latest_row}")
print(f"  daily_prices 最新日期: {latest_price_date}")

conn.close()
if has_null:
    print(f"\n❌ 有發現 NULL 值，請檢查 update_all_tech_indicators.py")
    sys.exit(1)
else:
    print(f"\n✅ 全部驗證通過")
