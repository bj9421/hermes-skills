# xfinance 評估報告 (2026-07-13)

**結論：不建議用於台股資料管線，也無法取代 yfinance 作為通用 fallback。**

## 測試項目

| 項目 | 結果 |
|------|------|
| 來源庫 | `xfinance` v0.4.1 (alpha) |
| 安裝方式 | `uv pip install xfinance httpx[http2]` |
| 測試標的 | AAPL (美股)、2330.TW (台股) |
| 測試 API | `Ticker().history(period='5d')` |

## 失敗原因

### 1. 真實錯誤被遮蔽（陷阱）
表面報 `name 'gen' is not defined`，實際是 Monkey-patch router 後才揭露各 source 的真實錯誤。若只看表面錯誤會誤以為是 Python 語法問題而浪費時間。

### 2. Yahoo Finance → HTTP 429 Rate Limit
此容器 IP 已被 Yahoo Finance 限流。即使等 60s 再打，同 IP 仍可能馬上又被 ban。用 yfinance 跑 1880+ 檔時沒這問題，顯示 xfinance 的 UA/header 或請求模式觸發了不同的 rate limiting threshold。

### 3. Stooq → Cloudflare JS Challenge + 無 .TW 支援
- Stooq 現在有 Cloudflare 抗 bot 保護，回傳 JS Challenge 而非 CSV
- xfinance 的 `_EXCHANGE_SUFFIX` 沒有 `.TW` mapping，`2330.TW` 被誤轉為 `2330.tw.us`
- 即使加上 mapping 也過不了 Cloudflare

### 4. ECB → 僅限外匯配對（預期行為）
### 5. Binance → 僅限加密幣（預期行為）

## 適用性總結

| 因子 | 狀態 |
|------|------|
| Yahoo 限流 | ❌ 此容器 IP 被擋 |
| Stooq Cloudflare | ❌ 自動化無法抓取 |
| 台股覆蓋 (`.TW`) | ❌ 無此 mapping |
| 錯誤訊息品質 | ⚠️ 誤導性強，需 monkey-patch router 才能揭露 |
| 是否需要 auth key | ✅ 不需要（但已無關緊要） |
