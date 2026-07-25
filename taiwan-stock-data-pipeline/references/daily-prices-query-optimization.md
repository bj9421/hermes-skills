# daily_prices 查詢優化 — 固定日期 Join vs Window Function

## 背景

`daily_prices` 表有 **1,532,344 rows / 1,925 stocks**（1.5M 筆）。最常做的查詢是：「每檔股票最新兩筆收盤價 & 漲跌幅」。

## 兩種寫法

### ❌ 慢：ROW_NUMBER Window Function（8.47s）

```sql
WITH lp AS (
    SELECT stock_code, date, close,
           ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY date DESC) rn
    FROM daily_prices WHERE close IS NOT NULL
)
SELECT curr.stock_code, curr.close AS price,
       (curr.close - prev.close) / prev.close * 100 AS change_pct
FROM lp curr
JOIN lp prev ON curr.stock_code = prev.stock_code AND prev.rn = 2
WHERE curr.rn = 1
ORDER BY curr.close DESC LIMIT 100;
```

**問題：** ROW_NUMBER scan 整個表（1.5M rows），即使只取 LIMIT 100。

### ✅ 快：固定日期 Self-Join（0.037s, 229× faster）

```python
latest = db.execute("SELECT MAX(date) FROM daily_prices WHERE close IS NOT NULL").fetchone()[0]
prev   = db.execute(
    "SELECT DISTINCT date FROM daily_prices WHERE close IS NOT NULL AND date < ? ORDER BY date DESC LIMIT 1",
    (latest,)
).fetchone()[0]

cur = db.execute("""
    SELECT curr.stock_code, curr.close AS price,
           (curr.close - prev.close) / prev.close * 100 AS change_pct
    FROM daily_prices curr
    JOIN daily_prices prev ON curr.stock_code = prev.stock_code AND prev.date = ?
    WHERE curr.date = ? AND curr.close IS NOT NULL AND prev.close IS NOT NULL
    ORDER BY curr.close DESC LIMIT 100
""", (prev, latest))
```

**原理：** `date = ?` 過濾讓 SQLite B-tree index 直接定位到兩天的資料範圍，只需讀 2 × 1925 = 3,850 rows 而非 1.5M。

## 適用條件

- 全市場交易日一致（TWSE/TPEX 多數交易日相同）
- 要查「最新 vs 前一日」這種固定時間點比較
- 不適用於每檔股票各自不同最新日期的場景（如 suspended 股票）
- 極少數 suspend 股票會被自動排除（curr.close IS NOT NULL）

## 當偏移量無法固定時

如果需要「每檔自己的最新 2 筆」（不同日期），可使用 correlated subquery 替代 window function：

```sql
SELECT curr.stock_code, curr.close,
       prev.close AS prev_close,
       (curr.close - prev.close) / prev.close * 100 AS change_pct
FROM daily_prices curr
JOIN daily_prices prev ON curr.stock_code = prev.stock_code
    AND prev.date = (SELECT MAX(date) FROM daily_prices p2 WHERE p2.stock_code = curr.stock_code AND p2.date < curr.date)
WHERE curr.date = (SELECT MAX(date) FROM daily_prices p3 WHERE p3.stock_code = curr.stock_code)
    AND curr.close IS NOT NULL AND prev.close IS NOT NULL;
```

但效能約 0.3–0.5s（仍優於 window function 但不如固定日期 join）。
