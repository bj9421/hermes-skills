#!/usr/bin/env python3
"""Measure Yahoo-only coverage over the full active universe.

Blocks FinMind (requests.get) so we measure ONLY Yahoo success.
Prints progress every 100 stocks and pickles results to /tmp/yahoo_cov_progress.pkl
(keys: stock_code -> {"inc":bool,"bal":bool,"cf":bool}).

Run:
  cd /opt/data/projects/taiwan-stock-cashflow-api
  .venv/bin/python3 /opt/data/skills/taiwan-stock-data-pipeline/scripts/measure_yahoo_coverage.py
"""
import sys, os, time, pickle

# Ensure project imports resolve even when run from elsewhere
PROJ = "/opt/data/projects/taiwan-stock-cashflow-api"
sys.path.insert(0, PROJ)
os.chdir(PROJ)

import requests

# --- Block ALL real network so we measure Yahoo-only (Yahoo is fetched via yfinance,
#     not requests.get; FinMind uses requests.get, so blocking it = pure Yahoo path) ---
_orig_get = requests.get
def _blocked(*a, **k):
    raise RuntimeError("network blocked for coverage test")
requests.get = _blocked

from screening.screener_db import get_active_universe
import financial_analyzers as fa
import cashflow_analyzer as cf
# make sure the analyzers' internal requests.get is also blocked
fa.requests.get = _blocked
cf.requests.get = _blocked

OUT = "/tmp/yahoo_cov_progress.pkl"

def main():
    universe = get_active_universe()
    results = {}
    t0 = time.time()
    for i, s in enumerate(universe, 1):
        code = s["stock_code"]
        try:
            inc = fa.IncomeAnalyzer().analyze(code).get("success")
            bal = fa.BalanceAnalyzer().analyze(code).get("success")
            cfr = cf.CashFlowAnalyzer().analyze_stock(code).get("success")
        except Exception:
            inc = bal = cfr = False
        results[code] = {"inc": bool(inc), "bal": bool(bal), "cf": bool(cfr)}
        if i % 100 == 0:
            ok = sum(1 for v in results.values() if v["inc"] and v["bal"] and v["cf"])
            print(f"[{i}/{len(universe)}] all3={ok} ({time.time()-t0:.0f}s)", flush=True)
            pickle.dump(results, open(OUT, "wb"))
    pickle.dump(results, open(OUT, "wb"))
    all3 = sum(1 for v in results.values() if v["inc"] and v["bal"] and v["cf"])
    print(f"\nDONE: {all3}/{len(results)} = {all3/len(results)*100:.1f}% all-3-tables (Yahoo-only)")

if __name__ == "__main__":
    main()
