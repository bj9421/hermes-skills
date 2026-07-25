#!/usr/bin/env python3
"""
OHLC 快速診斷腳本 (Quick Diagnostic)

當 --full 超時或遇到日期 bug 時使用。
1) 使用正確的 get_yesterday()（修復週一 bug）
2) 只抽樣 50 支（~1-2 分鐘），避免 API timeout
3) 比對 DB close vs twstock API close
"""
import sqlite3, twstock, time, sys
from datetime import datetime, timedelta

# === Corrected get_yesterday() — only adjust weekends ===
yesterday = datetime.now().date() - timedelta(days=1)
if yesterday.weekday() == 5:   # Saturday -> Friday
    yesterday -= timedelta(days=1)
elif yesterday.weekday() == 6: # Sunday -> Friday
    yesterday -= timedelta(days=2)

print(f"Target date: {yesterday} (weekday={yesterday.weekday()})")

conn = sqlite3.connect('/opt/data/taiwan_stocks.db', timeout=60)
c = conn.cursor()

c.execute("""
    SELECT DISTINCT stock_code FROM screen_cache
    WHERE price IS NOT NULL AND price > 0
    ORDER BY RANDOM() LIMIT 50
""")
stocks = [r[0] for r in c.fetchall()]
print(f"Sampled: {len(stocks)} stocks\n")

matched = mismatched = errors = 0
suspicious = []

for i, code in enumerate(stocks, 1):
    c.execute("SELECT close FROM daily_prices WHERE stock_code=? AND date=?",
              (code, yesterday.isoformat()))
    row = c.fetchone()
    db_close = row[0] if row else None

    try:
        s = twstock.Stock(code)
        data = s.fetch_from(yesterday.year, yesterday.month)
        api_ohlc = None
        for d in data:
            if d.date.date() == yesterday:
                api_ohlc = {
                    "open": float(d.open) if d.open else None,
                    "high": float(d.high) if d.high else None,
                    "low": float(d.low) if d.low else None,
                    "close": float(d.close) if d.close else None,
                }
                break
    except Exception:
        api_ohlc = None

    if api_ohlc and api_ohlc["close"] and api_ohlc["close"] > 0:
        api_close = api_ohlc["close"]
        if db_close is not None:
            dev = abs(db_close - api_close) / api_close
            if dev <= 0.01:
                matched += 1
            else:
                mismatched += 1
                suspicious.append((code, db_close, api_close, f"{dev:.1%}"))
        else:
            errors += 1
            suspicious.append((code, "DB_missing", api_close, "no_db_record"))
    else:
        errors += 1

    time.sleep(1.0)
    if i % 10 == 0:
        print(f"  Progress: {i}/{len(stocks)}")
        sys.stdout.flush()

conn.close()

print("\n" + "=" * 50)
print(f"OHLC Quick Diagnostic ({yesterday})")
print(f"  Sampled:    {len(stocks)}")
print(f"  Matched:    {matched}")
print(f"  Mismatched: {mismatched}")
print(f"  Errors:     {errors}")
print("=" * 50)
if suspicious:
    print(f"\nSuspicious ({len(suspicious)}):")
    for code, db, api, reason in suspicious:
        print(f"  {code}: DB={db}, API={api} ({reason})")
else:
    print("\nNo anomalies found.")
