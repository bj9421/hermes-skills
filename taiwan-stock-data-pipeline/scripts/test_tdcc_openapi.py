#!/usr/bin/env python3
"""測試 TDCC OpenAPI 端點可用性。"""
import subprocess, json

def test_endpoint(path, name):
    url = f"https://openapi.tdcc.com.tw{path}"
    r = subprocess.run(
        ['curl', '-s', '-L', '--connect-timeout', '10', url],
        capture_output=True, text=True
    )
    status = "✅" if r.returncode == 0 and len(r.stdout) > 100 else "❌"
    print(f"{status} {name}: {len(r.stdout)} bytes")
    return r.stdout

if __name__ == "__main__":
    print("=== TDCC OpenAPI 端點測試 ===")
    test_endpoint("/v1/opendata/1-1", "1-1 (證券基本資料)")
    test_endpoint("/v1/opendata/2-41", "2-41 (ETF月分析)")
    test_endpoint("/v1/opendata/2-22", "2-22 (上市保管異動)")
    test_endpoint("/v1/opendata/3-2", "3-2 (境外基金基本資料)")
