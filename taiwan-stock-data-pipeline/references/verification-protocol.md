# 資料驗證協定 (Data Verification Protocol)

> 每次對技術指標計算腳本進行修改後，需執行的標準驗證流程。

## 隨機抽樣交叉驗證（80 檔）

這是最低驗證標準，由使用者明確定義。

```python
# 語意：從 screen_cache 抽 80 檔隨機
# 對每檔：從 daily_prices 原始資料重算 MA5/10/20/60 + volume_ratio + volume_change
# 比較：DB 值與重算值，誤差 > 0.02 即視為 mismatch

codes = [r[0] for r in db.execute(
    'SELECT stock_code FROM screen_cache ORDER BY RANDOM() LIMIT 80'
).fetchall()]
```

**Gate condition:** 560 次個別指標比對 (80×7)，mismatch = 0 才可通過。

## 全量驗證（1,925 檔）

首次上線、修正全局 bug（如 reverse() 索引錯誤）後必須執行。

- 範圍：全部 1,925 檔
- 檢查項：MA5 / MA10 / MA20 / MA60 / BBmid / volume_ratio / volume_change
- 比對次數：約 13,475 次
- 實測時間：~10 秒（RPi4）
- **Gate condition:** 13,475 次比對全部通過，零 mismatch

## 跨表對應檢查

```sql
-- 確保 screen_cache 無遺漏股票
SELECT COUNT(*) FROM (
    SELECT DISTINCT stock_code FROM daily_prices
    EXCEPT
    SELECT DISTINCT stock_code FROM screen_cache
) AS missing;
-- 期望結果：0
```

## NULL 完整性檢查

```sql
-- 逐一檢查 15 個指標欄位，預期全部為 0
SELECT COUNT(*) FROM screen_cache WHERE rsi_14 IS NULL;
SELECT COUNT(*) FROM screen_cache WHERE volume_ratio IS NULL;
-- (依此類推所有指標欄位)
```

## 何時執行

| 情境 | 驗證層級 |
|:-----|:---------|
| 修改指標計算公式 | 全量 (1925) + 跨表對應 |
| 修改 DB schema 或 INSERT/UPDATE 邏輯 | 全量 |
| 修改爬蟲邏輯（不影響指標計算） | 80 檔隨機 |
| 每日 cron 更新後（例行性） | NULL 完整性 + 跨表對應 (快速) |
