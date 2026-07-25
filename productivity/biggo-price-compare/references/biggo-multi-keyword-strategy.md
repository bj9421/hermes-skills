# BigGo 多關鍵字拼湊策略

## 問題

BigGo 是 CSR 架構，單一關鍵字搜尋頁只能拿到 16-60 筆商品（實際 HTML 結構更少，靠 JS 動態載入）。無法分頁（`?page=N` 會重導向），所以需要其他方式擴大覆蓋率。

## 解決方案：多關鍵字拼湊

用 5 個相關但不同的關鍵字分別搜尋 BigGo，然後合併去重。

### 實測數據（以 B5/泛醇為例）

| 關鍵字 | 獨立商品數 |
|--------|-----------|
| B5 | 20 |
| 泛醇 | 19 |
| panthenol | 8 |
| 膏狀 | 15 |
| 維他命B5 | 6 |
| **總和（含重複）** | **68** |
| **去重後** | **30-45** |

- 單一關鍵字：12-20 筆
- 5 個關鍵字：60-68 筆（含重複）
- 去重後：30-45 筆獨立商品

### 實作流程

```python
# 1. 定義相關關鍵字群
keywords = ["B5", "泛醇", "panthenol", "膏狀", "維他命B5"]

# 2. 逐個搜尋 + extract
all_products = []
seen_purls = set()

for kw in keywords:
    # Step 1: Search
    search_result = anysearch_search(f'site:biggo.com.tw "{kw}"')
    biggo_url = search_result['url']
    
    # Step 2: Extract
    extract_result = anysearch_extract(biggo_url)
    
    # Step 3: Parse products
    products = parse_biggo_extract(extract_result)
    
    # Step 4: Dedup + limit
    for p in products:
        if p['purl'] not in seen_purls and len(all_products) < 30:
            seen_purls.add(p['purl'])
            all_products.append(p)
```

### 關鍵字選擇原則

1. **同義詞** — 中文名 + 英文名（例：泛醇 / panthenol）
2. **別名** — 常見俗稱（例：B5 / 維他命B5）
3. **形態描述** — 產品物理特性（例：膏狀、粉末、液態）
4. **品牌名** — 如果有特定品牌目標
5. **成分全名** — 化學全名（例：1,3-丁二醇）

### 注意事項

- ⚠️ 去重用 purl（完整 URL），不是商品名稱
- ⚠️ 去重後限制 30 筆，避免處理時間過長
- ⚠️ 不同關鍵字可能搜到完全不同的商品（不是所有關鍵字都會重疊）
- ⚠️ 某些關鍵字可能回傳很少結果（如英文名在台灣市場不常見）
