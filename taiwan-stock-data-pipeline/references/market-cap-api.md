# Market Cap — TWSE Open API Reference

## Endpoint

```
GET https://openapi.twse.com.tw/v1/opendata/t187ap03_L
```

**Response:** JSON array of 1089 records (上市公司總市值基本資料)

**Key fields:**
| Field | Description | Example |
|-------|-------------|---------|
| `公司代號` | Stock code | `2330` |
| `公司簡稱` | Stock name | `台積電` |
| `已發行普通股數或TDR原股發行股數` | Outstanding shares | `25930380482` |
| `實收資本額` | Paid-in capital (NTD) | `259303804820` |

## Market Cap Calculation

```
market_cap (億) = close_price × outstanding_shares / 100,000,000
```

## Integration

In `app.py` `/api/heatmap` endpoint:

```sql
SELECT curr.stock_code, sm.stock_name, sm.industry, sm.market_cap,
       curr.close AS price,
       ROUND((curr.close - prev.close) / prev.close * 100, 2) AS change_pct
FROM daily_prices curr
JOIN daily_prices prev ON curr.stock_code = prev.stock_code AND prev.date = ?
JOIN stock_meta sm ON curr.stock_code = sm.stock_code
WHERE curr.date = ? AND curr.close IS NOT NULL AND prev.close IS NOT NULL
  AND sm.market_cap IS NOT NULL
ORDER BY sm.market_cap DESC LIMIT 100
```

## Notes

- Outstanding shares change infrequently (capital increases/decreases). Fetch monthly.
- This API covers listed (TWSE) companies only (~1089). For TPEX (上櫃), use a different endpoint.
- Some stocks (DR, ETF, warrants) won't have market_cap — they're excluded from the API naturally.
