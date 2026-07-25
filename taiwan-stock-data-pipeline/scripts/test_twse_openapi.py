#!/usr/bin/env python3
"""測試 TWSE OpenAPI 端點可用性。"""
import subprocess, json

def test_endpoint(url, name):
    r = subprocess.run(
        ['curl', '-s', '--connect-timeout', '10', url],
        capture_output=True, text=True
    )
    status = "✅" if r.returncode == 0 and len(r.stdout) > 100 else "❌"
    print(f"{status} {name}: {len(r.stdout)} bytes")
    return r.stdout

if __name__ == "__main__":
    print("=== TWSE OpenAPI 端點測試 ===")
    test_endpoint(
        "https://openapi.twse.com.tw/v1/api/data/t187ap03_L?selectType=all&response=json",
        "t187ap03_L (基本資料)"
    )
    test_endpoint(
        "https://openapi.twse.com.tw/v1/api/data/STOCK_DAY_ALL?selectType=20250709&response=json",
        "STOCK_DAY_ALL (日成交)"
    )
    test_endpoint(
        "https://openapi.twse.com.tw/v1/api/data/t187ap06_L_ci?selectType=all&response=json",
        "t187ap06_L_ci (損益表)"
    )
    test_endpoint(
        "https://openapi.twse.com.tw/v1/api/data/t187ap07_L_ci?selectType=all&response=json",
        "t187ap07_L_ci (資產負債表)"
    )
