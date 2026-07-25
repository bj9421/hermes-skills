# BigGo 分頁限制與 HTML 結構分析

## 實測結論

BigGo 比價網（biggo.com.tw）是 **CSR（Client-Side Rendering）架構**，所有搜尋結果由 JavaScript 動態載入，傳統 HTTP 請求只能拿到骨架 HTML。

### 分頁行為

| 測試 | 結果 |
|------|------|
| Page 1 搜尋 | 正常返回 16-60 筆獨立商品（依關鍵字熱門度）|
| Page 2（`?page=2`）| ❌ 重導向回 Page 1 |
| Page 3+ | ❌ 同上 |
| API endpoint | 無公開分頁 API |

**結論：BigGo 不支援分頁抓取，無法透過 URL 參數取得第 2 頁以後的資料。**

### HTML 結構（逐行模式）

BigGo 搜尋頁的 HTML 是 CSR 骨架，關鍵元素：

```
Line N:   [產品名稱](/r/?i=平台&id=ID&purl=...)   ← 名稱和 URL 在同一行
Line N+2: $價格                                     ← 緊接下 2-3 行內
Line N+3: 折扣資訊（如 0~1%）                       ← 可選
Line N+4: 平台連結                                  ← [Yahoo購物中心](/store/?i=...)
```

#### 產品名稱解析規則
- 規格單位直接寫在產品名稱中，**沒有獨立規格行**
- 例：`正勤 1 3-丁二醇 5公斤 1個` → "5公斤" 在 name 字串內
- 提取方式：`re.search(r'(\d+\s*(?:g|kg|ml|l|公克|公斤|斤))', name)`

#### purl 結構
```
/r/?i=tw_shopee&id=12345&purl=https%3A%2F%2Fshopee.tw%2Fproduct%2F...
```
- `i` = 平台代碼（tw_shopee, tw_yahoo 等）
- `id` = BigGo 內部 ID
- `purl` = 編碼後的真實商品頁 URL（需 URL decode）

#### 廣告標記
- 以 `/r/?` 開頭的名稱行是廣告標記截斷 URL，不是產品名
- 過濾條件：名稱 < 8 字 或 名稱以 `/r/?` 開頭 → 排除

### 商品連結數量對比

| 方法 | 連結數 | 備註 |
|------|--------|------|
| curl（原始 HTML）| ~13 個 | 只有 SSR 骨架 |
| anysearch extract（LLM 轉換）| ~48 個 | 多抓 ~4 倍，但仍不完整 |
| 瀏覽器完整渲染 | 更多 | CSR 動態載入全部商品 |

**結論：即使是最強的 HTML 解析也拿不到全部商品，多關鍵字拼湊是必要的補充策略。**

### 結論與建議

1. **不要嘗試分頁** — BigGo 做了重導向封鎖
2. **不要假裝手機 UA** — CSR 不依賴 User-Agent，手機版 HTML 甚至更少
3. **接受限制** — 單頁抓 16-60 筆，用多關鍵字彌補
4. **去重必做** — 同一商品可能出現多次（廣告 + organic），依 purl 去重
