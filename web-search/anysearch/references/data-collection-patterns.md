# AnySearch 資料採集模式 (Data Collection Patterns)

## 動機：為何用 anysearch 取代付費 API？

許多資料採集場景依賴付費第三方 API（Apify、SerpAPI 等），
但這些資料往往在公開網頁上就有，只需 `extract` 解析即可。

| 面向 | 付費 API（如 Apify Actor） | AnySearch extract（直接爬） |
|------|---------------------------|----------------------------|
| **成本** | 月費或按次計費 | **零成本**（僅 token 查詢配額） |
| **擴充性** | 每多一個目標 = 多耗額度 → 易超支 | 不因目標數量倍增收費 |
| **欄位數** | 回傳結構化 JSON，欄位豐富 | 需從 HTML parse 目標欄位（多寫 20 行 code） |
| **頻率** | 受額度限制（$5/月 → 約 600 次） | 不受額度限制（robots.txt 仍要尊重） |
| **反爬** | API 處理好 proxy/代理 | 看目標網站封鎖程度（可用 `anysearch extract` 等 proxy） |

## ⚠️ 適用場景判斷（先做 pre-flight 再 commit）

**不適合用 anysearch extract 的情況（以下任一成立即放棄）：**

| 阻礙類型 | 如何檢測 | 例子 |
|----------|---------|------|
| **JS Rendering（SPA）** | `extract` 回傳的內容幾乎只有 JS bundle，無目標文字 | Instagram location pages, Twitter/X pages |
| **Login Wall** | 匿名訪問只看到登入畫面 | Instagram profile/location pages, Facebook pages |
| **Cloudflare / CAPTCHA** | extract 回傳 "Just a moment..." 或 verify 頁面 | TikTok, 許多 ASN 封鎖站 |
| **API gate** | 瀏覽器可看但 API 呼叫需 token/signature | Instagram GraphQL (query_hash + 登入 cookie) |

### ✅ Pre-flight 測試腳本

在投入 parse 邏輯之前，先用一條命令確認 extract 拿得到內容：

```bash
python3 /opt/data/skills/web-search/anysearch/scripts/anysearch_cli.py extract \
  "https://target-site.com/page-of-interest" 2>&1 | grep -v '^$' | wc -l
```

- **回傳 < 5 行有效文字** → 高度懷疑 JS-rendered / login wall
- **內容含 "just a moment"、"verify"、"cf-challenge"** → Cloudflare block
- **內容只有 meta title + empty body** → SPA，需 browser rendering

### 適用判斷流程

```
目標在公開網頁？
  ├─ 否 (logged-in only, API-gated) → 用付費 API 或放棄
  ├─ 是 → extract 預檢
  │    ├─ extract 回傳內容含目標數據
  │    │    └─ 就繼續 parse HTML
  │    └─ extract 回傳空/JS-only/登入畫面
  │         └─ anysearch extract 不適用
```

---

## 注意事項（通用）

1. **robots.txt** — 即使工具不強制，君子協議建議遵守 `Crawl-delay`
2. **同一目標爬太頻繁** — 建議最小間隔 ~2s/request，每日一次是安全頻率
3. **parse 脆性** — 目標 HTML 結構改變可能 break，需加 monitoring（欄位驟降為 0 時警報）
4. **fallback 設計** — 爬失敗時應保留前一日資料而非插 null

---

## 實際案例 1：純靜態 HTML ✅

**可爬的目標範例** — Wikipedia、公開政府資料、新聞文章、README.md 純文本端點：

```python
URLS = {
    "台北101": "https://en.wikipedia.org/wiki/Taipei_101",
}

for name, url in URLS.items():
    result = subprocess.run(
        ["python3", "/opt/data/skills/web-search/anysearch/scripts/anysearch_cli.py",
         "extract", url],
        capture_output=True, text=True
    )
    # Wikipedia 的 text content 在 extract 結果中可直接拿
    first_paragraph = result.stdout.split("\n\n")[0]
```

---

## 實際案例 2：IG 景點 — 不適用 extract ❌

### 背景

Instagram location pages (e.g. `instagram.com/explore/locations/{id}/`) 是 **fully JS-rendered SPA**，
server 回傳只有空殼 HTML + JavaScript bundle。任何未登入的訪問：

| 嘗試方法 | 結果 |
|---------|------|
| `anysearch extract` | 只拿得到 `<title>` — "Taipei 101 on Instagram • Photos and Videos" |
| `curl + GraphQL query_hash` | 回傳 `"Please wait a few minutes before you try again"` + require_login=true |
| `curl i.instagram.com/api/v1/locations/{id}/info/` | 空 — 需 session cookie |
| `oembed API` | 空 |
| `curl + Chrome UA` | 599KB 全部是 JS bundles，零文字內容含 media_count |
| 第三方 viewer (Gramhir, Dumpor, ImgInn) | 全 404 或被封 |

### 結論

| 面向 | IG 景點頁 | 建議 |
|------|-----------|------|
| **anysearch extract** | ❌ 無法取得 media_count 等結構化資料 | 放棄此路徑 |
| **anysearch search** | ✅ 可發現 IG location 頁面的存在（從 URL+title） | 可用於 location ID discovery |
| **付費 API** | ✅ Apify `louisdeconinck/instagram-location-stats-scraper` 仍可行 | $5/月，100+ 景點可能超支 |
| **替代方案** | 改用搜尋引擎行量、Trip.com 提及數等**間接指標** | 零成本，但非 IG 原生數據 |

### 教訓

1. 不要假設 URL 能開 = extract 拿得到資料 — **必先 pre-flight**
2. JS-rendered SPA + login wall 雙重封鎖 = anysearch extract 無用武之地
3. `search` 與 `extract` 能力不同：search 找到頁面 ≠ extract 能讀取內容

---

## 標準架構模式（用於 extract 可爬的目標）

```python
import sqlite3, subprocess, re
from datetime import date

URLS = {
    "目標A": "https://example.com/data/1",
    "目標B": "https://example.com/data/2",
}

DB_PATH = "data/stats.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

for name, url in URLS.items():
    result = subprocess.run(
        ["python3", "/opt/data/skills/web-search/anysearch/scripts/anysearch_cli.py",
         "extract", url],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(f"SKIP {name}: extract failed")
        continue

    # 從 extract 文字解析目標欄位
    value = parse_target_field(result.stdout)

    c.execute("""
        INSERT OR REPLACE INTO stats
        (name, snapshot_date, value)
        VALUES (?, ?, ?)
    """, (name, date.today().isoformat(), value))

conn.commit()
```

---

## 關鍵區別總結

| 使用模式 | 可行場景 | 不可行場景 |
|----------|---------|-----------|
| `extract` 拿結構化數據 | 純 HTML 頁 (gov data, wiki, blog) | JS-rendered SPA (IG, Twitter, FB) |
| `extract` 發現 | 搜尋引擎已有索引的公開頁面 | 需登入、paywall、反爬強 |
| `search` 發現 URL | 所有被搜尋引擎收錄的頁面 | 無 SEO 的 SPA、私有 API 端點 |
