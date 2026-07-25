#!/opt/data/.venv/bin/python
"""TWSE/TPEX API rate limit probe.

Tests the actual rate limit of TWSE/TPEX public stock data endpoints
by gradually increasing request speed and checking for 429 responses.

Usage:
    python scripts/rate_limit_test.py         # full test (10 min)
    python scripts/rate_limit_test.py --quick  # quick test (60→120→180 rpm)
"""

import sys
import time
import twstock
from datetime import datetime

# Test levels: (label, rpm, interval_sec)
if "--quick" in sys.argv:
    LEVELS = [
        ("60 rpm  (1.00s)", 60, 1.0),
        ("120 rpm (0.50s)", 120, 0.5),
        ("180 rpm (0.33s)", 180, 0.33),
    ]
else:
    LEVELS = [
        ("60 rpm  (1.00s)", 60, 1.0),
        ("120 rpm (0.50s)", 120, 0.5),
        ("180 rpm (0.33s)", 180, 0.33),
        ("240 rpm (0.25s)", 240, 0.25),
        ("300 rpm (0.20s)", 300, 0.20),
    ]

STOCKS_PER_LEVEL = 10
RETRY_429_WAIT = 60  # seconds to wait if we hit a 429

twstock.twse.update()
twstock.tpex.update()
all_codes = [c for c, i in twstock.codes.items() if i.type == "股票"]
test_codes = all_codes[:30]  # use first 30 stocks as test subjects

print(f"TWSE/TPEX Rate Limit Probe — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"Test pool: {len(test_codes)} stocks")
print("=" * 50)

for label, rpm, interval in LEVELS:
    print(f"\n--- Testing {label} ---")
    errors_429 = 0
    errors_other = 0
    last_req = 0.0

    for i in range(STOCKS_PER_LEVEL):
        code = test_codes[i % len(test_codes)]
        elapsed = time.time() - last_req
        if elapsed < interval:
            time.sleep(interval - elapsed)
        last_req = time.time()

        try:
            stock = twstock.Stock(code)
            data = stock.fetch_from(2026, 7)
            records = len(data) if data else 0
            status = "✓" if records > 0 else "∼"
            print(f"  [{i+1}/{STOCKS_PER_LEVEL}] {code}: {records} records {status}", flush=True)
        except Exception as e:
            estr = str(e)
            if "429" in estr or "Too Many Requests" in estr:
                errors_429 += 1
                print(f"  [{i+1}/{STOCKS_PER_LEVEL}] {code}: ⛔ 429 RATE LIMITED!", flush=True)
                print(f"  ⏸  Pausing {RETRY_429_WAIT}s before continuing...", flush=True)
                time.sleep(RETRY_429_WAIT)
            else:
                errors_other += 1
                print(f"  [{i+1}/{STOCKS_PER_LEVEL}] {code}: ⚠ {estr[:80]}", flush=True)

    status = "✅ PASS" if errors_429 == 0 else f"⛔ FAIL ({errors_429} × 429)"
    print(f"  → {label}: {status} (other errors: {errors_other})")

print("\n" + "=" * 50)
print("Test complete.")
