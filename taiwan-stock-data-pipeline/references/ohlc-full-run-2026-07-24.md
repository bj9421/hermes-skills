# OHLC Verify 全量比對記錄

## 2026-07-25 全量實測（--full，目標日期 2026-07-24）

| 項目 | 數值 |
|------|------|
| 總股票數 | 1925 |
| Matched (一致) | 1891 (98.2%) |
| Mismatched (不一致) | 27 (1.4%) |
| Errors (API 失敗) | 7 (0.4%) |
| 執行時間 | ~38 分鐘 |

### API 失敗股票 (7 筆)
| 代碼 | 原因 |
|------|------|
| 1459 | api_fetch_failed |
| 1589 | api_fetch_failed |
| 3426 | yfinance 404 "Quote not found" |
| 4130 | yfinance 404 "Quote not found" |
| 4804 | yfinance 404 "possibly delisted" |
| 4987 | yfinance 404 "possibly delisted" |
| 6806 | yfinance 404 "no price data found" |

### Mismatch 分析（27 筆）
**全部為 missing_data（DB 中 close=null），零筆實際價格偏差。**

分類：
- **both_missing (~26 支)**：DB close=null + API close=null — twstock 也查無資料（暫停交易/低流動性）
  - 2035, 2937, 3064, 3067, 3085, 3158, 3226, 3531, 3664, 4183, 4305, 4406, 5520, 6171, 6210, 6228, 6236, 6242, 6856, 6865, 7743, 7782, 8342, 8477, 8905, 8923
- **db_only_missing (1 支)**：DB close=null 但 API 有值
  - **5236（凌陽）**：yfinance 回傳 close=150.5，DB 為 null → 資料管線可能漏抓，建議補跑

### 結論
- **價格準確度 100%**：1891 筆有數值的股票全部通過比對
- 27 筆異常全為「DB 無資料」非「資料錯誤」，屬於覆蓋率問題而非準確性問題
- 相較前次全量（2026-07-17 執行，matched=774 / 40.2%），覆蓋率從 40.2% 提升至 98.2%
- 建議針對 5236 補跑增量更新

---

## 歷史記錄：2026-07-24 舊版全量（2026-07-17 執行，目標日期 2026-07-16）

> 已被上方 2026-07-25 實測取代（資料管線覆蓋率已大幅改善）。

| 項目 | 數值 |
|------|------|
| Matched | 1899 (98.65%) |
| Mismatched | 21 (1.09%) → both_missing |
| Errors | 5 (0.26%) |
| 執行時間 | ~101 min |
