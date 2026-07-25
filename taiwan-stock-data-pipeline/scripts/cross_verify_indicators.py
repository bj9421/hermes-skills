#!/usr/bin/env python3
"""
交叉驗證 screen_cache 技術指標 — 從 daily_prices 原始資料重算並比對。

使用方式:
    # 預設：抽 80 檔隨機交叉比對（快速檢查）
    python3 cross_verify_indicators.py

    # 全量 1,925 檔全部比對（~10 秒，RPi4）
    python3 cross_verify_indicators.py --full

比對項目: MA5/10/20/60, BBmiddle == MA20, volume_ratio, volume_change
"""
import sqlite3
import numpy as np
import sys
import os
import time

DB_CANDIDATES = [
    os.environ.get("STOCK_DB_PATH"),
    "/opt/data/taiwan_stocks.db",
    os.path.join(os.path.dirname(__file__), "../../taiwan_stocks.db"),
]
DB_PATH = next((p for p in DB_CANDIDATES if p and os.path.exists(p)), None)
if not DB_PATH:
    print("❌ Cannot find taiwan_stocks.db. Set STOCK_DB_PATH or run from project root.")
    sys.exit(1)

FULL_MODE = "--full" in sys.argv
SAMPLE_SIZE = 80 if not FULL_MODE else None  # None = all


def calc_rsi(arr, period=14):
    if len(arr) < period + 1:
        return None
    rec = arr[-(period + 1) :]
    gains, losses = [], []
    for i in range(1, period + 1):
        ch = rec[i] - rec[i - 1]
        gains.append(ch if ch > 0 else 0)
        losses.append(abs(ch) if ch < 0 else 0)
    ag = np.mean(gains)
    al = np.mean(losses)
    return 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 2)


def calc_macd(arr, fast=12, slow=26):
    if len(arr) < slow:
        return None
    ema_f, ema_s = arr[0], arr[0]
    for p in arr:
        ema_f = p * (2 / (fast + 1)) + ema_f * (1 - 2 / (fast + 1))
        ema_s = p * (2 / (slow + 1)) + ema_s * (1 - 2 / (slow + 1))
    return round(ema_f - ema_s, 2)


def verify_stock(code, db):
    """Verify one stock's indicators against raw daily_prices. Returns list of mismatch messages."""
    rows = db.execute(
        "SELECT date, close, volume FROM daily_prices WHERE stock_code = ? ORDER BY date DESC",
        (code,),
    ).fetchall()
    p = [r[1] for r in rows if r[1] is not None]
    v = [r[2] for r in rows if r[2] is not None]
    if not p:
        return ["no price data"]
    p.reverse()
    v.reverse()

    sc = db.execute(
        """SELECT ma5,ma10,ma20,ma60,rsi_6,rsi_12,rsi_14,
                  macd,bollinger_middle,volume_ratio,volume_change
           FROM screen_cache WHERE stock_code=?""",
        (code,),
    ).fetchone()
    if not sc:
        return ["no screen_cache entry"]

    mismatches = []
    T = 0.02  # tolerance

    # MA
    for period, idx, name in [(5, 0, "MA5"), (10, 1, "MA10"), (20, 2, "MA20"), (60, 3, "MA60")]:
        if sc[idx] is not None and len(p) >= period:
            calc = round(float(np.mean(p[-period:])), 2)
            if abs(sc[idx] - calc) > T:
                mismatches.append(f"{name}: DB={sc[idx]}, calc={calc}")

    # Bollinger middle == MA20
    if sc[2] is not None and sc[8] is not None and abs(sc[2] - sc[8]) > T:
        mismatches.append(f"BBmid≠MA20: mid={sc[8]}, ma20={sc[2]}")

    # Volume ratio
    if sc[9] is not None and len(v) >= 6:
        avg5 = float(np.mean(v[-6:-1]))
        if avg5 > 0:
            calc = round(v[-1] / avg5, 2)
            if abs(sc[9] - calc) > T:
                mismatches.append(f"VR: DB={sc[9]}, calc={calc}")

    # Volume change
    if sc[10] is not None and len(v) >= 6:
        avg5 = float(np.mean(v[-6:-1]))
        if avg5 > 0:
            calc = round((v[-1] / avg5 - 1) * 100, 2)
            if abs(sc[10] - calc) > T:
                mismatches.append(f"VC: DB={sc[10]}, calc={calc}")

    return mismatches


def main():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    t0 = time.time()

    if FULL_MODE or SAMPLE_SIZE is None:
        codes = [r[0] for r in cur.execute("SELECT stock_code FROM screen_cache").fetchall()]
        label = f"all {len(codes)}"
    else:
        codes = [
            r[0]
            for r in cur.execute(
                "SELECT stock_code FROM screen_cache ORDER BY RANDOM() LIMIT ?",
                (SAMPLE_SIZE,),
            ).fetchall()
        ]
        label = f"{len(codes)} random"

    print(f"🔍 Cross-verifying {label} stocks from {DB_PATH}")
    print()

    total_checks = 0
    all_mismatches = {}

    for code in codes:
        mismatches = verify_stock(code, db)
        if mismatches:
            all_mismatches[code] = mismatches
        total_checks += 7  # MA5+MA10+MA20+MA60+BBmid+VR+VC

    elapsed = time.time() - t0

    print(f"\n{'='*50}")
    print(f"  Stocks checked: {len(codes)}")
    print(f"  Individual checks: {total_checks}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Mismatches: {len(all_mismatches)}")
    print(f"{'='*50}")

    if all_mismatches:
        print("\n❌ MISMATCHES:")
        for code, ms in sorted(all_mismatches.items()):
            for m in ms:
                print(f"  {code}: {m}")
        sys.exit(1)
    else:
        print("\n✅ All indicators verified correct.")

    db.close()


if __name__ == "__main__":
    main()
