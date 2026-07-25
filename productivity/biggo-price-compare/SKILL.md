---
name: biggo-price-compare
description: "BigGo 比價單價分析：從 biggo.com.tw 搜尋商品，提取價格資料與個別賣場連結，計算並比較各賣家單位價格，輸出排行表。"
version: 1.4.0
author: xiaomi
platforms: [android, linux]
tags: [biggo, price-comparison, unit-price, shopping, taiwan]
---

# BigGo 單價比較分析

## Overview
透過 anysearch 從 BigGo 比價網（biggo.com.tw）搜尋商品，extract 個別賣場連結，提取價格與規格，自動計算單位價格並排出最划算的賣家。

## Trigger Conditions
- 用戶提到 BigGo、比價、找便宜、找賣家、單價比較
- 需要比較台灣網購平台上化工原料、保養品原料等商品的各賣家價格
- 用戶想找特定商品「哪家最便宜」

## Workflow

### Step 1：搜尋 BigGo（取得關鍵字 + 價格）
BigGo 搜尋頁會顯示商品總數和平均價格，先抓取這些基本資料：
```
python3 <skill_dir>/../anysearch/scripts/anysearch_cli.py \
  search "<keyword>" site:biggo.com.tw
```

### Step 2：Extract 個別賣場連結（⚠️ 必做步驟）
搜尋結果只有 BigGo 搜尋頁 URL，不是個別商品頁。必須 extract 每個搜尋結果頁取得真實賣場連結：
```
python3 <skill_dir>/../anysearch/scripts/anysearch_cli.py \
  extract "<BigGo搜尋頁URL>"
```

### Step 3：從 extract 輸出解析 purl 取得真實商品連結
BigGo 搜尋頁的完整 HTML 結構（逐行模式）：
```
Line N:   [產品名稱](/r/?i=平台&id=ID&purl=...)   ← 名稱和 URL 在同一行！
Line N+2: $價格                                     ← 緊接下 2-3 行內
Line N+3: 折扣資訊（如 0~1%）                       ← 可選
Line N+4: 平台連結                                  ← [Yahoo購物中心](/store/?i=...)
```
⚠️ 規格單位直接寫在產品名稱中！ 沒有獨立規格行。
- 例：正勤 1 3-丁二醇 5公斤 1個 → "5公斤" 在名稱內
- 提取方式：`re.search(r'(\d+\s*(?:g|kg|ml|l|公克|公斤|斤))', name)`

#### 解析流程
1. 正則匹配：`r'^\[([^\]]+)\]\(/r/\?i=(tw_\w+)&id=(\d+)&purl=(https?%3A[^)\s"]+)'`
2. 商品名稱條件：
   - 長度 >= 8 字
   - 不能以 `/r/?` 開頭（這是廣告標記行的截斷 URL）
   - 不能有 type tag（這是圖片 alt text）
   - 長度 <= 200（避免截斷過長 URL）
3. 去重：依 purl 完整內容（`seen_purls.add(purl_enc)`）
4. 價格提取：從名稱行往後看最多 6 行，找 `$\d[\d,]*`
5. 過濾無關商品：排除「書」「肥皂」「乳霜」「禮盒」等

#### 過濾規則
- 排除 keywords：書, 簡體書, 繁體書, 教材, 教科書, 肥皂, 乳霜, 禮盒, 護手霜, 衛生紙
- 保留 keywords：關鍵字本身（丁二醇、玫瑰果油等）

### Step 4：提取價格資料（從 Step 1 snippet + Step 3 連結）
辨識每個商品的：
- 商品名稱（品名、品牌、型號）
- 規格（重量/容量/數量）
- 售價 ($NT)
- 賣家名稱
- 來源平台（蝦皮/Yahoo/露天/Coupang/大直/三民/博客來/iopenmall/ybuy）
- 個別真實商品連結

⚠️ 價格單位可能混雜 — 有的 $X,XXX，有的 X,XXX 不含 $，有的有折扣。

### Step 5：自動計算單位價格
依照商品特性選擇適合的計算方式：
- 重量型（克/公斤）：$ ÷ g = $/g
- 容量型（毫升/公升）：$ ÷ ml = $/ml
- 數量型（個/入/盒）：$ ÷ 數量 = $/個
- 大包裝優先：通常 1kg > 500g > 100g 更划算

> ⚠️ 同商品不同濃度不可直接比較（如純玫瑰果油 vs 玫瑰果複方精華）

### Step 6：排序輸出與推薦（⚠️ 必備完整商品頁連結）
按單位價格由低到高排列，必須包含完整可點擊的商品頁連結：

| # | 平台 | 售價 | 規格 | 單價 | 🔗 商品連結 |
|---|------|------|------|------|------------|
| 1 | Coupang | $2,380 | 1kg | $2.38/g | [完整商品名稱](https://真實商品頁URL) |

⚠️ 連結不能截斷：顯示 purl 必須完整可用，不可顯示 "..." 或半截 URL。
⚠️ 每次修改都要驗證：價格、規格、商品名稱、連結四項缺一不可。

### Telegram 輸出格式（⚠️ 精簡模式：省 token）
**只回 Top 5 + 結論**，完整清單放 Obsidian。

```
🏆 [關鍵字] 比價結果（共 N 筆）

🥇 [賣家] [規格] $[價格] → $[單位價格]
🥈 [賣家] [規格] $[價格] → $[單位價格]
🥉 [賣家] [規格] $[價格] → $[單位價格]
4️⃣ [賣家] [規格] $[價格] → $[單位價格]
5️⃣ [賣家] [規格] $[價格] → $[單位價格]

📄 完整 N 筆含連結：Obsidian 搜「[關鍵字]」
```

⚠️ Telegram 回覆不超過 10 行，連結全部放 Obsidian。

### Step 7：存入 Obsidian（⚠️ 必做步驟）
比價完成後，**必須**將結果存入 Obsidian vault 供使用者日後查詢。

#### 檔案路徑
```
/opt/data/obsidian-vault/比價/<關鍵字>-BigGo-<YYYY-MM-DD>.md
```
- 例：`B5膏狀原料-BigGo-2026-07-24.md`

#### 檔案格式（⚠️ 連結必須完整可點擊）
```markdown
# <關鍵字> — BigGo 比價結果

> 📅 搜尋日期：YYYY-MM-DD
> 🔍 關鍵字：<關鍵字>
> 🔗 BigGo 搜尋頁：<BigGo搜尋頁URL>

---

## 🏆 膏狀/液態 分類排行

### 🥇 #1 <商品完整名稱>
- 平台：<平台>｜售價：$<價格>｜規格：<規格>｜單價：$<單位價格>
- 🔗 <完整商品頁URL>

### 🥈 #2 <商品完整名稱>
- 平台：<平台>｜售價：$<價格>｜規格：<規格>｜單價：$<單位價格>
- 🔗 <完整商品頁URL>

（每筆商品都要有 🔗 連結）

---

## 🏆 推薦
| 需求 | 推薦 | 說明 |
|------|------|------|
| 大量最便宜 | 🥇 ... | ... |
| 少量試用 | ... | ... |

> 📌 注意事項
> 🔗 BigGo 比價搜尋頁連結
```

#### 連結提取規則
- 從 extract 輸出的 purl 參數解碼後取得真實商品頁 URL
- **蝦皮**：`https://shopee.tw/product/<shop_id>/<item_id>`
- **Yahoo拍賣**：`https://tw.bid.yahoo.com/item/<item_id>`
- **Coupang**：`https://www.coupang.com/vp/product/<item_id>`
- **iOPEN Mall**：`https://mall.iopenmall.tw/...`（直接用 purl）
- 每筆商品**必須**附上完整可點擊連結，不可省略或截斷

#### 存檔後權限
```bash
chmod -R 777 /opt/data/obsidian-vault/比價/
```
確保手機 Syncthing 同步後可讀取。

---

## 第 1 頁商品數與分頁限制

| 測試結果 | BigGo 行為 |
|----------|-----------|
| Page 1 獨立商品 | 16-60 筆（依關鍵字熱門度）|
| Page 2 (?page=2) | ❌ 重導向回 Page 1 |
| CSR 商品總量 | 原始 HTML 只有 ~13 個連結，實際更多靠 JS 渲染 |
| 結論 | 無法透過 API 拿取更多頁面資料 |

### ⚡ 建議限制前 30 筆 + 多關鍵字拼湊
```python
# 去重範例
seen_purls = set()
products = []
for p in all_products:
    if p['purl'] not in seen_purls and len(products) < 30:
        seen_purls.add(p['purl'])
        products.append(p)

# 多關鍵字拼湊（解決 CSR 渲染不足的問題）
keywords = ["B5", "泛醇", "panthenol", "膏狀", "維他命B5"]
all_results = [extract_biggo(kw) for kw in keywords]
unique = merge_and_dedup(all_results)
```
原因：
- BigGo 搜尋頁同一商品可能出現在多個平台（蝦皮/Yahoo），purl 相同但連結不同
- 去重後的獨立商品約 16-60 筆
- 取前 30 筆已足夠比價，避免浪費處理時間
- CSR 限制: anysearch extract 只能解析 HTML，無法執行 JavaScript，會漏掉動態載入的商品
- 解決方案: 使用多個相關關鍵字組合搜尋，拼湊出更多商品

## Performance Profile (實測基準)

| Step | Command | 耗時 | 備註 |
|------|---------|------|------|
| 1. Search | anysearch search "site:biggo.com.tw <kw>" | ~1s | 幾乎瞬間 |
| 2. Extract | anysearch extract "<URL>" | 2-3s/頁 | 最大瓶頸 |
| 3. 去重+限制 30 筆 | Python set() | <1s | 依 purl 去重 |
| 4-5. Parse & Calc | Python parsing | <1s | 腳本解析 |
| Total | Full flow | 5-10s | 單頁 + 去重 |

⚠️ 單頁獨立商品通常 16-60 筆，取前 30 筆已夠用
⚠️ BigGo 是 CSR (Client-Side Rendering) — anysearch extract 調用外部 API (anysearch.com)，後端 LLM 做 HTML→Markdown 轉換，比 curl raw HTML 多抓 ~4 倍連結 (48 vs 13)。若要抓更多，必須做多關鍵字拼湊。

## Multi-Keyword Strategy (已驗證有效)
5 個關鍵字組合可抓到 60-68 筆獨立商品：
```python
keywords = ["B5", "泛醇", "panthenol", "膏狀", "維他命B5"]
# 各關鍵字貢獻: B5=20, 泛醇=19, panthenol=8, 膏狀=15, 維他命B5=6
all_results = [extract_biggo(kw) for kw in keywords]
unique = merge_and_dedup(all_results)  # 去重取前30筆
```
- 單一關鍵字 ≈ 12-20 筆
- 5 個關鍵字總和 ≈ 60-68 筆（含重複），去重後 ≈ 30-45 筆獨立商品

## Pitfalls
- ⚠️ 搜尋結果的 URL 不是個別商品頁，必須 extract 才能取得真實連結
- ⚠️ BigGo ?page=N 會重導向回第 1 頁 — 不分頁，換關鍵字取得更多資料
- 模擬手機 User-Agent 無效 — BigGo CSR 不依賴 UA 改變內容，手機版 HTML 甚至更少連結
- anysearch extract 不支援自訂 header（--header）— 傳 UA 參數會導致拿不到任何資料
- 同個商品出現在多處（廣告 vs organic）— 必須用 purl 去重
- 規格單位直接寫在產品名稱中！沒有獨立規格行。例：正勤 1 3-丁二醇 5公斤 1個 → 5公斤在 name 內
- ⚠️ 名稱為廣告標記時會以 /r/? 開頭，長度極長，必須過濾掉（條件：名稱 < 8 字或名稱以 /r/? 開頭）
- 同名的 /r/? 連結出現多次（廣告標記 + 實際商品），第一次匹配的常是 URL 本身而非產品名，需過濾
- 過濾原則：寬鬆 > 過度嚴格 — 只排除 簡體書, 繁體書, 教科書, 教材, 文具, 錶, 收納。不要預設排除非目標原料商品

### ⚠️ 修改 Skill 前必須先分析舊版
- 改 skill 前先讀完整舊版：使用 skill_view(name) 讀取完整舊版 SKILL.md，不可一步到位全推翻重寫
- 一次只改一個重點，確認 OK 後再改下一個
- 大幅改版前必須警告提醒：告訴用戶要改動太多內容
- 不要在改過程中遺漏連結或商品數據：每次修改都要驗證輸出
- 像 Ha-Powers 流程一樣：讀舊版 → 提計劃 + TODO → 確認後才動手改

## References
See references/biggo-pagination-reality.md for detailed pagination and HTML structure analysis.
See references/biggo-multi-keyword-strategy.md for the multi-keyword combing workaround for CSR limitation.
See references/biggo-extract-vs-curl-comparison.md for extract API vs raw curl link count comparison.
