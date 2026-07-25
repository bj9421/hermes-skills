# 技術指標管線 — 參考資料

## 資料庫結構

### screen_cache 表（技術指標儲存處）

```sql
CREATE TABLE screen_cache (
    stock_code        TEXT PRIMARY KEY,
    cached_at         TIMESTAMP,
    total_score       REAL,      -- 基本面總分
    -- 基本面欄位（略）
    
    -- 技術指標欄位（由 update_all_tech_indicators.py 寫入）
    rsi_14            REAL,      -- RSI 14 日
    rsi_6             REAL,      -- RSI 6 日
    rsi_12            REAL,      -- RSI 12 日
    ma5               REAL,      -- 5 日均線
    ma10              REAL,      -- 10 日均線
    ma20              REAL,      -- 20 日均線
    ma60              REAL,      -- 60 日均線
    macd              REAL,      -- MACD DIF 值
    bollinger_upper   REAL,      -- 布林帶上軌
    bollinger_middle  REAL,      -- 布林帶中軌（SMA20）
    bollinger_lower   REAL,      -- 布林帶下軌
    bollinger_width   REAL,      -- 布林帶寬度百分比
    volume_ratio      REAL,      -- 量比（當日/5日均量）
    volume_change     REAL,      -- 量變化率 %
    volume            REAL,      -- 成交量
    price             REAL       -- 最新收盤價
);
```

### 計算邏輯

所有計算都在 `taiwan-stock-cashflow-api/screening/update_all_tech_indicators.py`：

| 指標 | 方法 | 參數 |
|:-----|:------|:------|
| **RSI** | Wilder's smoothed RSI | 6 / 12 / 14 日 |
| **MA** | Simple Moving Average (np.mean) | 5 / 10 / 20 / 60 |
| **MACD** | EMA(12) - EMA(26) | Smoothing: 2/(n+1) |
| **Bollinger** | SMA20 ± 2σ | Width% = (U-L)/M × 100 |
| **Volume Ratio** | 今日量 / 前 5 日均量 | latest = volumes[-1]; base = mean(volumes[-6:-1]) |
| **Volume Change** | (今日量 / 5日均量 − 1) × 100 | |

## 執行效率

| 指標 | 實測 |
|:-----|:-----|
| 全量 1925 檔 | ~12 秒（numpy 2.5.0） |
| 依賴 | numpy 2.5.0 |
| DB 鎖政策 | `PRAGMA busy_timeout=60000`（腳本單次連線，無併發） |

## 選股策略定義

策略儲存於 `screen_strategies` 表，條件在 `criteria_json` 欄位。實際篩選邏輯寫在 `auto_screen_and_notify.py`：

```python
strategies = {
    "rsi_oversold":    lambda s, c: s["rsi_14"] <= c.get("max_rsi", 30) and s["total_score"] >= c.get("min_total", 20),
    "MACD_CROSS":      lambda s, c: s["macd"] > 0 and s["rsi_14"] <= c.get("max_rsi", 65) and s["total_score"] >= c.get("min_total", 15),
    "VOLUME_BREAKOUT": lambda s, c: s["vol_change"] >= c.get("min_volume_change", 30) and s["total_score"] >= c.get("min_total", 15),
    "MA_DIVERGENCE":   lambda s, c: s["total_score"] >= 15 and 1.1 <= s["ma5"]/s["ma60"] <= 1.3,
    "TREND_FOLLOWER":  lambda s, c: s["vol_change"] >= 20 and s["macd"] > 0 and s["total_score"] >= 15,
    "CONSERVATIVE_GROWTH": lambda s, c: s["total_score"] >= 15 and s["bb_width"] <= 8 and 40 <= s["rsi_14"] <= 60,
    # ... 共 14 種
}
```

### ⚠️ 已知 Bug 修復記錄

**reverse() 索引混淆 (2026-07-08)**
`update_all_tech_indicators.py` 從 DB 以 `ORDER BY date DESC` 查詢（最新在前），計算前會 `prices.reverse()` 和 `volumes.reverse()` 轉為 ASC（最舊在前）。
但 `calculate_volume_ratio()` 和內聯的 `volume_change` 邏輯**仍用 DESC 索引**：
- `volumes[0]` → 抓到**最舊**的量（應為 `volumes[-1]`）
- `volumes[1:6]` → 抓到**最舊第 2~6 天**（應為 `volumes[-6:-1]`）

**影響範圍：** 全部 1925 檔股票的 volume_ratio 和 volume_change 數值皆錯，RSI/MA/MACD 不受影響（他們用 ASC 索引正確）。
**修復：** 2026-07-08 patch → 重跑全量後驗證 NULL 歸零 ✅

**教訓：** 資料排序變更（DESC⇄ASC）後，務必審查所有依賴索引位置的計算邏輯，特別是「最新筆」統一套用 `[0]`（DESC）或 `[-1]`（ASC），並加上明確註解。

## 相關檔案

| 檔案 | 說明 |
|:-----|:------|
| `taiwan-stock-cashflow-api/screening/update_all_tech_indicators.py` | 全量計算 |
| `taiwan-stock-cashflow-api/screening/update_tech_indicators.py` | 增量計算（限已有分數的股票） |
| `taiwan-stock-cashflow-api/screening/auto_screen_and_notify.py` | 策略篩選 + Telegram 推播 |
| `taiwan-stock-cashflow-api/screening/screen_strategies.sql` | 策略初始化 SQL |
