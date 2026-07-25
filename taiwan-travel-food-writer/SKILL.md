---
name: taiwan-travel-food-writer
description: "自動產出台灣景點+在地美食文章，歸檔至 Obsidian、Mail2Blogger 直接 MX 寄送草稿（不經帳密）"
version: 3.7.0
author: Hermes Agent
platforms: [linux]
---

# 台灣景點美食自動產文技能

## 觸發方式
- 對話中說「寫一篇XX景點美食介紹」
- cron job 排程自動產出

## 前置：目錄結構

```bash
mkdir -p /opt/data/auto-content/articles
```

## 步驟

### 0.5 資訊查證原則

- **預設行為：** 所有資訊**必須查證至少 1–2 個獨立資料源**，確認無誤後才寫入文章。不可憑既有知識直接撰稿。
- **查證工具：** 使用 `smart-search` 技能進行資訊檢索（anysearch CLI 優先 → DDG MCP 備援）。不可跳過 anysearch 直接走 DDG，即使 DDG 的 MCP 工具在你的工具清單中「可見」。
- **查證上限：** 每項查證最多比對 **3 個來源**即收斂，不要無限延伸。
- **停止訊號（覆寫用）：** 使用者說「夠了」「不要搜尋了」「用現有資料寫就好」時，**立即停止所有搜尋**。手中已有多少資料就用多少。
  - 已確認的項目 → 直接寫入文章
  - 未確認的項目 → 保留但加註「資訊未確認」或 ⚠️ 標示
  - 排隊中但尚未執行的查證 → 直接取消

### 1. 選擇主題
從台灣熱門景點 / 夜市 / 老街 / 秘境中選擇一個主題。
優先挑選當季適合造訪的地點（夏天選避暑/海邊，冬天選溫泉/火鍋）。

### 2. 撰寫文章
產出結構化 Markdown 文章。

**⚠️ 規則：一律不寫價格**
這是使用者硬性規則 — 所有旅遊美食文**禁止出現任何價格資訊**（數字+元/NT$/塊）。推薦欄只列品項名稱，不標價。敘述、標題中也不提金額。連「銅板價」「佛心價」「實惠」等暗示價格的形容詞也避免。

**格式：**
當使用者指定「只要地址及營業時間」時，使用**僅地址+營業時間**模板。

```markdown
# [景點名稱] — 在地美食推薦

## 📍 景點介紹
（200-300 字簡介，地理位置、特色、適合族群）

## 🚗 交通方式
（大眾運輸、自行開車、停車資訊）

## ⏰ 營業資訊
（開放時間、門票/入場費、建議停留時間）

## 📸 景點推薦
（列出 3–5 個景點或美食，每個含：）
### N️⃣ [名稱]
- **Google Maps：** [完整地址](https://maps.google.com/?q=完整地址)
- **營業時間：** 週一至週日 HH:MM–HH:MM（特殊公休日備註）
- **推薦理由：** （簡短描述，無價格字眼）

## 💡 小提醒
（注意事項、最佳造訪時段、建議行程安排）

## 🔗 延伸閱讀
（相關附近景點）
```

> ⚠️ 這條是硬性規則，非選擇性模式。一切價格資訊（NT$、元、$/塊、價位、銅板價、佛心價）都禁止。

### 3. 儲存文章

**直接寫入 Obsidian Vault（推薦，因 blogger_send.sh 從 vault 讀取）：**

```bash
# 直接存到 obsidian-vault (blogger_send.sh 直接餵文件名即可)
/opt/data/obsidian-vault/17uu/
    └── 景點名稱_YYYY-MM-DD.md

# ⚠️ 手機端 uid 1000 vs Docker hermes 使用者，務必開權限
chmod -R 777 /opt/data/obsidian-vault/17uu/
```

**替代：輸出到 auto-content/articles/**
```bash
/opt/data/auto-content/
└── articles/
    └── 景點名稱_YYYY-MM-DD.md
```

### 4. 歸檔至 Obsidian（選擇性）

如果要在 Obsidian 筆記庫中留存備份：

```bash
# 建立目標資料夾
mkdir -p /opt/data/obsidian-vault/[主題]

# 複製文章
cp /opt/data/auto-content/articles/景點名稱_YYYY-MM-DD.md /opt/data/obsidian-vault/[主題]/

# ⚠️ 權限修正（Docker 內 hermes 使用者 vs 手機端 uid 1000）
chmod -R 777 /opt/data/obsidian-vault/[主題]/
```

### 5. 回報
回傳文章摘要給使用者。

### 6. 發佈至 Blogger（Mail2Blogger — 無密碼直接 MX 投遞）

> ✅ **直接 MX 投遞（port 25）對純文字郵件完全可行。**
> 實測驗證：純文字信件經由 `gmr-smtp-in.l.google.com:25` 直接投遞，SMTP 回傳 250 OK，信件確實進入 Blogger 草稿匣。

**前置條件：**
- Blogger 後台已啟用「透過電子郵件張貼文章」→ https://draft.blogger.com
- 設定為「將電子郵件另存成草稿文章」（預設）
- 知道自己的 Blogger 秘密郵箱地址（如 `bj9421.217uu@blogger.com`）
- 寄件者信箱（From header）設為 Gmail 地址即可，不需認證

**一鍵發文腳本（推薦，不需密碼）：**

```bash
bash /opt/data/scripts/blogger_send.sh 東港
```

腳本自動比對文件名、走直接 MX、不帶圖片。

**底層指令（直接）：**
```bash
uv run python3 /opt/data/scripts/blogger_direct.py /opt/data/obsidian-vault/[主題]/文章.md --no-images
```

**流程：**
1. 讀取 Obsidian Markdown 文章
2. 從 `# 標題` 解析文章標題
3. （預設）跳過圖片嵌入，僅轉換 Markdown → HTML
4. DNS 查詢 blogger.com 的 MX 記錄 → 優先 MX `gmr-smtp-in.l.google.com`
5. 直接連線 `gmr-smtp-in.l.google.com:25` → EHLO → MAIL FROM → RCPT TO → DATA
6. 寄送到 Blogger 秘密郵箱 → 自動存為草稿

**驗證：** 到 https://draft.blogger.com 檢查草稿匣

**使用者偏好（重要）：**
- ❌ **不帶圖片** — 純文字/HTML 即可。大圖會導致 MX 投遞失敗。
- ❌ **不要 Google 帳密** — 不需要 App Password 或 OAuth。

**替代方案（含圖片時使用 SMTP 認證）：**
若日後需要帶圖發文，用 `smtp.gmail.com:587` + App Password：
```bash
uv run python3 /opt/data/scripts/blogger_auth.py post 文章.md
```
需要一次性設定 App Password（密碼存本機），且圖檔需控制 <1MB/張。

**已知陷阱：**
- **純文字 MX OK，大圖 MX 失敗：** 實測結論 — 無圖信件走 port 25 直達草稿匣；含 base64 圖片（>2MB）的 HTML 信件 Google 無聲丟棄。
- 直接 MX 的信件**無 SPF/DKIM 簽章**，純文字可過但大附檔會被 spam filter 攔截。
- Email 發文不支援 Blogger 標籤/分類設定 → 分類需手動在 Blogger 後台調整。
- 設定檔路徑固定為 `/opt/data/.config/blogger/`（Docker 環境中 `~` 指向不可寫的 `/root`）。

**定時排程（自動發布）：**

由於直接 MX 不需密碼，可直接使用 `blogger_direct.py`：
```bash
hermes cron create --schedule "0 8 * * *" --name "每日旅遊文章→Blogger" \
  --prompt "從 Obsidian vault 挑一篇草稿，用 bash /opt/data/scripts/blogger_send.sh [文件名] 發佈到 Blogger（不帶圖）" \
  --skills taiwan-travel-food-writer
```

## 5.5 參考查詢工具

文章寫作前可用 `blogref` 快速查詢 26K 筆觀光資料：

```bash
# 完整說明
bash /opt/data/scripts/blogref --help

# 列出縣市資料量
bash /opt/data/scripts/blogref cities

# 查台南推薦景點（指定分類/關鍵字）
bash /opt/data/scripts/blogref attractions --city 臺南市 --category 文化類
bash /opt/data/scripts/blogref attractions --city 花蓮縣 --category 自然風景類

# 查美食（依料理分類）
bash /opt/data/scripts/blogref restaurants --city 臺中市 --cuisine 火鍋

# 跨表關鍵字搜尋（一次搜景點+餐飲+旅宿+活動）
bash /opt/data/scripts/blogref search 老街 --city 臺南市
bash /opt/data/scripts/blogref search 牛肉麵

# 縣市總覽（四表一覽）
bash /opt/data/scripts/blogref all --city 臺南市

# 查住宿
bash /opt/data/scripts/blogref hotels --city 花蓮縣 --type 民宿

# 查看分類代碼對照
bash /opt/data/scripts/blogref categories
```

輸出格式為美觀的 Emoji 卡片，可直接複製貼入文章。

> 完整分類代碼對照表（景點 28 類 + 餐飲 28 類 + 旅宿 5 類 + 活動 30 類）見 `references/tourism-category-codes.md`。

## 6.0 資料來源：觀光署景點開放資料

> 自 v3.5.0 起，推薦優先使用交通部觀光署官方開放資料作為景點資訊來源，取代純靠搜尋引擎查證。

### 景點資料集

**資料來源：** 交通部觀光署 — 景點 - 觀光資訊資料庫  
**開放平臺：** <https://data.gov.tw/dataset/7777>  
**下載網址（每日更新）：**
```
https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Attraction-json.zip
```

**資料量：** 6,095 筆景點（2026-07 資料）、全台 22 縣市全覆蓋  
**更新頻率：** 每日  
**授權：** 政府資料開放授權條款（免費商用）

### 資料結構

ZIP 內含三個 JSON 檔：

| 檔案 | 說明 | 大小 |
|------|------|------|
| `AttractionList.json` | 景點基本資料（6,095 筆） | ~16MB |
| `AttractionServiceTimeList.json` | 營運時間資料 | ~64KB |
| `AttractionFeeList.json` | 收費資料 | ~35KB |

### 每筆景點關鍵欄位

| 欄位 | 範例 | 用途 |
|------|------|------|
| `AttractionName` | 太平山國家森林遊樂區 | 文章主題 |
| `Description` | 蹦蹦車、溫泉、高山湖泊... | 正文素材（200–500 字） |
| `PositionLat / PositionLon` | 24.557, 121.499 | 地圖嵌入 |
| `PostalAddress.City` | 宜蘭縣 | 縣市分類 |
| `PostalAddress.StreetAddress` | 太平巷58之1號 | 地址欄 |
| `AttractionClasses` | [16] | 分類過濾 |
| `Images[].URL` | https://...jpg | 配圖來源（最多 16 張） |
| `WebsiteURL` | recreation.forest.gov.tw | 來源查證 |
| `Telephones` | (03)9770766 | 聯絡資訊 |
| `ServiceTimeInfo` | 06:00–20:00 | 營業時間 |
| `TrafficInfo` | 國道5號→省道台7線... | 交通方式 |
| `ParkingInfo` | 小型車100元 | 停車資訊 |
| `Tags` | ["賞楓","溫泉","雲海"] | 關鍵字 |
| `SocialMediaURLs` | facebook.com/... | 社群分享 |

### 分類系統（28 類）

| 代碼 | 分類 | 數量 | 適合 IG 監控 |
|:----:|------|:----:|:-----------:|
| 11 | 自然風景類 | 866 | ✅ |
| 12 | 遊憩類 | 1,508 | ✅ |
| 8 | 國家風景區類 | 377 | ✅ |
| 16 | 森林遊樂區類 | 47 | ✅ |
| 9 | 休閒農業類 | 273 | ✅ |
| 10 | 溫泉類 | 46 | ✅ |
| 6 | 商圈商店類 | 260 | ✅ |
| 25 | 藝文場館類 | 260 | ✅ |
| 15 | 都會公園類 | 171 | ✅ |
| 1 | 文化類 | 1,783 | 依需求 |
| 3 | 文化資產類 | 775 | 依需求 |
| 4 | 宗教廟宇類 | 563 | 依需求 |
| 19 | 公園綠地類 | 178 | ✅ |
| 20 | 觀光遊樂業類 | 9 | 依需求 |
| ... | 共 28 類 | ... | |

完整分類對照見 `references/tourism-bureau-attractions-api.md`。

### 取用流程

```bash
# 1. 下載最新資料
curl -sL "https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Attraction-json.zip" \
  -o /tmp/attractions.zip

# 2. 解壓縮（Python，embed 環境無 unzip）
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/attractions.zip', 'r') as z:
    z.extractall('/tmp/attractions_data')
"

# 3. 讀取（注意編碼為 utf-8-sig）
import json
with open('/tmp/attractions_data/AttractionList.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)
attrs = data['Attractions']  # list[dict]
```

### 在其他步驟中的應用

- **步驟 1（選擇主題）：** 用此資料庫列出特定縣市 + 特定分類的景點，搭配當季性過濾
- **步驟 2（撰寫文章）：** 直接從官方資料抄錄 `Description`、`TrafficInfo`、`ServiceTimeInfo` 等欄位，**仍需查證 1–2 個補充來源**確認時效性
- **步驟 3（儲存）：** 可在文章中加註 `資料來源：交通部觀光署開放資料` 提高可信度
- **步驟 4（圖片處理）：** `Images[].URL` 可直接作為 blog 配圖來源

### 重要限制

- **無即時人潮資料：** 此為靜態景點資訊，不含即時人潮、擁擠程度。即時畫面需靠 CCTV（步驟 6.5）。
- **分類編碼非文字：** `AttractionClasses` 為數字代碼（1–27, 254），須對照分類表。
- **Description 長短不一：** 從 50 字到 900 字都有。短篇需額外搜尋補充。
- **圖片可能過時：** 官方圖片來自各管理處上傳，部分可能是數年前拍攝。

詳細 API 文件見 `references/tourism-bureau-attractions-api.md`。

## 6.6 嵌入景區即時影像（選擇性）

在 Blogger 文章中嵌入台灣景區 CCTV，讓讀者看到即時天氣與人潮。

### 影像類型

從 tw.live 研究發現，景區 CCTV 分兩種可嵌入類型：

| 類型 | Blogger 方式 | 代表景點 |
|---|---|---|
| **YouTube 直播** 🎥 | `<iframe>` 直接嵌入 | 阿里山、日月潭、墾丁 |
| **公路局快照** 📸 | `<img>` 戳圖（定時更新） | 太魯閣、省道路況 |

**始終優先 YouTube 直播** — 順暢串流、手機相容、一行語法搞定。

### YouTube 嵌入語法（Blogger HTML 模式）

```html
<iframe width="100%" height="400"
  src="https://www.youtube-nocookie.com/embed/VIDEO_ID?autoplay=1&mute=1&playsinline=1&rel=0&modestbranding=1"
  title="景區即時影像" frameborder="0"
  allow="autoplay; encrypted-media; gyroscope; picture-in-picture"
  allowfullscreen>
</iframe>
```

### 已確認的 YouTube ID

完整對照表（100+ 鏡頭）見 `references/cctv-taiwan-scenic.md`。以下為交通部觀光署 **13 個國家風景區**的官方頻道即時影像：

| 風景區分類 | 景點 | Video ID |
|-----------|------|:--------:|
| 🟦 東北角及宜蘭海岸 | 鼻頭服務區 | `4VBfBgnhJUE` |
| 🟦 東北角及宜蘭海岸 | 舊草嶺隧道(南口) | `Br1w0sIvO3U` |
| 🟦 東北角及宜蘭海岸 | 永鎮濱海驛站 | `HVcowpes0qA` |
| 🟦 東北角及宜蘭海岸 | 馬崗哨所 | `IZBAoy4OR-s` |
| 🟦 北海岸及觀音山 | 觀音山 4K | `Kbkn-TGoa_0` |
| 🟦 北海岸及觀音山 | 白沙灣 4K | `FbB8WDUXXqU` |
| 🟦 北海岸及觀音山 | 野柳地質公園 4K | `ZjuY4qKaj40` |
| 🟦 北海岸及觀音山 | 老梅綠石槽 | `Wefj3zbl-tI` |
| 🟦 北海岸及觀音山 | 和平島公園 4K | `g-T8NbF9xlQ` |
| 🟦 北海岸及觀音山 | 中角灣 4K | `iJphhU-iaTA` |
| 🟩 參山—獅頭山 | 峨眉湖 | `L9y1pwGktQg` |
| 🟩 參山—梨山 | 櫻緣丘 | `NhzycUzqwV8` |
| 🟩 參山—梨山 | 攬勝樓 | `R1RjtxkkxPw` |
| 🟩 參山—梨山 | 梨山賓館 | `v3Pbbu6v_is` |
| 🟩 參山—八卦山 | 彰化平原 | `RaTbGYKMUtk` |
| 🟩 阿里山 | 觸口遊客中心 | `8KnqJBf_dow` |
| 🟩 **日月潭** | **九蛙疊像平台** | `IZlB2NKZUI8` | 縮時影像 |
| 🟩 日月潭 | **達克拉哈自行車道** | `hd20XV2AtGk` | 縮時影像 |
| 🟧 西拉雅 | 曾文水庫 | `EH4V8IwFIp4` |
| 🟧 茂林 | 屏東平原眺景 | `iW2P7TM9SaY` |
| 🟧 大鵬灣 | 小琉球花瓶岩 | `tHAeigBuzSQ` |
| 🟪 花東縱谷 | 鯉魚潭 4K | `aaKOV4qkDHw` |
| 🟪 花東縱谷 | 赤科山 | `5GTFLN9gZrc` |
| 🟪 花東縱谷 | 六十石山 | `DliL9uMtPrI` |
| 🟪 花東縱谷 | 鹿野高台 4K | `rvc1klNIgQc` |
| 🟪 東部海岸 | 三仙台 | `dQ7Sd6PGLdA` |
| 🟪 東部海岸 | 都歷遊客中心 | `JhQuR77AR7U` |
| 🟪 東部海岸 | 大石鼻山 | `JkoXcXI04Qk` |
| 🟪 東部海岸 | 加路蘭遊憩區 | `AKl3F6cAY2Q` |
| 🩷 澎湖 | 觀音亭 360 4K | `tJSJMfxfivY` |
| 🩷 離島 | 馬祖南竿鐵堡 | `ifk2LtOKjSk` |

### 掃描新 Camera

**首選方法：直接爬官方 YouTube 頻道（最可靠，不依賴第三方）**

各風景區管理處在 YouTube 有官方頻道，直接爬 `/streams` 頁面即可取得最新即時影像 Video ID：

```bash
# 1. 從官方頻道取得所有即時串流 ID
curl -sL "https://www.youtube.com/@官方頻道名/streams" \
  | grep -oP 'watch\?v=[a-zA-Z0-9_-]{11}' | sort -u

# 2. 用 oembed API 驗證每個 Video ID 的標題與內容類別
curl -s "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=VIDEO_ID&format=json" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('title','?'))"
```

**已知官方頻道（國家風景區管理處）：**

| 風景區 | YouTube 頻道 |
|--------|-------------|
| 東北角及宜蘭海岸 | `@necoastnsa2903` |
| 北海岸及觀音山 | 北觀處頻道 |
| 參山（獅頭山/梨山/八卦山） | `@trimtnsa` |
| 花東縱谷 | `@ervnsa` |
| 東部海岸 | `@eastcoastnsa0501` |
| 澎湖 | `@ph-nsa` |
| 日月潭 | `@sunmoonlake362` |

**備用方法：tw.live 掃描**

當官方頻道不足時，可用 tw.live 補資料：

```bash
# 1. 先找 camera ID 列表（從分類頁面）
curl -sL "https://tw.live/<景點英文>/" | grep -oP '/cam/\?id=[^"&]+'

# 2. 從 camera 頁面取出 YouTube embed ID
#   方法 A：直接 curl（若無 Cloudflare 封鎖）
curl -sL "https://tw.live/cam/?id=<camera-id>" | grep -oP 'embed/[^"？]+'

#   方法 B：Wayback Machine 繞過 Cloudflare（推薦）
curl -sL "https://web.archive.org/web/2025/https://tw.live/cam/?id=<camera-id>" \
  | grep -oP 'youtube-nocookie\.com/embed/[^?"]+' | grep -v live_stream | head -1

#   方法 C：YouTube 搜尋（前兩者都失敗時）
encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('景點名稱 即時影像 live'))")
curl -sL -H 'User-Agent: Mozilla/5.0' "https://www.youtube.com/results?search_query=$encoded" \
  | grep -oP '"videoId":"[^"]*"' | sort -u | head -3
```

完整對照表（100+ 鏡頭）與詳細掃描說明見 `references/cctv-taiwan-scenic.md`。

### 多鏡頭 Blogger 文章布局範本（用 CSS Grid）

大量 iframe 並排時，使用 CSS grid 而非 `<table>` 以獲得更好的手機 RWD：

```html
<style>
.cam-grid { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
.cam-item { width: 400px; max-width: 100%; background: #f5f5f5; border-radius: 12px; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.cam-item h4 { margin: 0 0 8px 0; font-size: 15px; }
.cam-item iframe { width: 100%; height: 225px; border-radius: 8px; }
@media (max-width: 480px) { .cam-item { width: 100%; } .cam-item iframe { height: 200px; } }
.section-title { font-size: 20px; font-weight: bold; margin: 32px 0 16px 0; padding: 10px 16px; border-radius: 8px; color: white; display: inline-block; }
.section-north { background: #2c6e9c; }
.section-central { background: #4a7c4f; }
.section-south { background: #c47a3a; }
.section-east { background: #6b4c8a; }
.section-island { background: #a05070; }
</style>
```

參考 `references/cctv-taiwan-scenic.md` 有完整的 Blogger HTML 範本與區域分類樣式。

## 6.7 國家（自然）公園即時影像

此類別為內政部國家公園署轄下 **10 處國家(自然)公園**（不同於交通部觀光署的 13 處國家風景區）。

| 類型 | 國家公園 | 景點 | Video ID | 備註 |
|------|---------|------|:--------:|:----:|
| 🏔️ | **陽明山** | 擎天崗 360 全景 | `UX4FTHVXcz4` | |
| 🏔️ | 陽明山 | 擎天崗草原 | `6HeYP46CMgg` | |
| 🏔️ | 陽明山 | 二子坪停車場 | `d9KuXrPCWYU` | |
| ❄️ | **雪霸** | 汶水遊客中心 | `VgmWVBUsfGo` | 24h HD 直播 |
| ❄️ | 雪霸 | 雪見遊憩區 | `2KDE860OW_A` | |
| ❄️ | 雪霸 | 觀霧遊憩區 | `Isp6RQiuxNo` | |
| ❄️ | 雪霸 | 武陵遊憩區 | `aGOFDlySzoQ` | |
| ❄️ | 雪霸 | 櫻花鉤吻鮭實境秀 | `MsQy9yCNjOc` | 七家灣溪 |
| 🏔️ | **太魯閣** | 遊客中心 360 | `K3VZNxKt01o` | |
| 🗻 | **玉山** | (無 YouTube 直播) | — | ⚠️ 用 livecam.tw |
| 🌴 | **墾丁** | 船帆石 4K | `0lX9L16KCpU` | |
| 🌴 | 墾丁 | 船帆石沙灘 4K | `7WOJMh_eSfY` | |
| 🌴 | 墾丁 | 後壁湖 | `pmEp7abtH1o` | |
| 🌴 | 墾丁 | 墾丁大街南下 4K | `hrpwltQqtq0` | |
| 🌴 | 墾丁 | 墾丁大街牌樓 | `l0MykkrTvo4` | |
| 🌴 | 墾丁 | 黑枕藍鶲 Live | `489ngM5ehe0` | |
| 🏛️ | **金門** | 麒麟山森林公園 | `M4EJtf_iP8s` | |
| 🪸 | **東沙環礁** | (無公開直播) | — | ⚠️ 管制區 |
| 🐦 | **台江** | 七股賞鳥亭黑琵 | `sJyKI--gdnA` | |
| 🐒 | **壽山⛰️** | 情人觀景台 4K | `C03Itx8iSC0` | 國家自然公園 |
| 🏝️ | **南方四島** | (無公開直播) | — | ⚠️ 保護區 |

**搜尋法：** 國家公園的即時影像散布於各管理處 YouTube 頻道、地方縣市政府、以及第三方整合平台（livecam.tw, tw.live）。驗證流程同風景區（anysearch → oembed → livecam.tw 三方交叉比對）。

完整對照表與詳細說明見 `references/cctv-taiwan-national-parks.md`。

### 兩篇文章拆分建議

當一次要產出大量即時影像（如 13 風景區 + 10 國家公園 = 多達 50 支 iframe），建議拆為兩篇文章投遞：

- **篇章 A：** 13 處國家風景區（29+ 支）
- **篇章 B：** 10 處國家(自然)公園（19+ 支）

好處：單篇文章載入速度更快、讀者閱讀體驗更佳、Blogger 編輯器不會因過長而卡頓。

### 授權注意

YouTube 直播由各風景區管理處上傳，使用 YouTube embed 為公開標準功能，不需另外取得授權。政府 CCTV 為開放資料，一般使用無限制。

## 6.8 發布前 YouTube 失效檢查（品質閘門）

> ⚠️ **使用者會主動要求「檢查 youtube 源是否失效」** — 請在交付文章後主動跑驗證，不要等被提醒。這是每篇即時影像文章的必經品質閘門。

**核心問題：** HTTP 狀態碼不可靠 — oembed 和 embed 頁面對已刪除/私人/不存在的影片仍回 HTTP 200。必須檢查**頁面實際內容**才能辨識失效。

**三層驗證流程（實測 0 偽陽性）：**

```bash
# 建議使用 verify-youtube-ids.sh 腳本（已包裝所有邏輯）
bash /opt/data/skills/taiwan-travel-food-writer/scripts/verify-youtube-ids.sh ID1 ID2 ID3
```

若手動驗證，用以下 Python 腳本（比 bash loop 更可靠）：

```python
import urllib.request, json, sys

def check_video(vid):
    vid = vid.strip()
    reasons = []
    
    # ① oembed 基本檢查
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        title = data.get("title", "")
        if not title:
            reasons.append("oembed 無 title")
    except Exception as e:
        reasons.append(f"oembed 失敗: {str(e)[:60]}")
    
    # ② 縮圖檢查（最可靠靜態訊號）
    try:
        req = urllib.request.Request(
            f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        if "hqdefault" not in resp.geturl():
            reasons.append(f"縮圖非標準路徑")
    except Exception:
        reasons.append("縮圖 404")
    
    # ③ Embed videoId 出現次數（最可靠動態訊號 🎯）
    # 有效影片: videoId 在頁面中出現 ≥2 次
    # 不存在/已刪除: 只出現 1 次（僅 URL 本身）
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/embed/{vid}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="replace")
        count = html.count(vid)
        if count < 2:
            reasons.append(f"embed 頁面無影片資料 (vid 僅出現 {count} 次)")
    except Exception as e:
        reasons.append(f"embed 讀取失敗: {str(e)[:60]}")
    
    # 綜合判斷
    if not reasons:
        status = "✅ 有效"
    elif any("embed 頁面無影片資料" in r or "縮圖 404" in r for r in reasons):
        status = "❌ 失效"
    else:
        status = "⚠️ 可能有問題"
    
    return {"id": vid, "status": status, "title": title[:80] if title else "", "reasons": reasons}

if __name__ == "__main__":
    for vid in sys.argv[1:]:
        r = check_video(vid)
        print(f"{r['id']} → {r['status']} | {r.get('title','')}")
        for reason in r.get("reasons", []):
            print(f"    ⚠ {reason}")
```

**📌 各層驗證可信度對照：**

| 層級 | 檢查點 | 有效影片 | 失效影片 | 可靠度 |
|------|--------|---------|---------|--------|
| ① oembed | `GET oembed?url=...&format=json` | HTTP 200 + 有 title | 同 200（偽陽性⚠️） | 低 |
| **② 縮圖** | **`img.youtube.com/vi/{VID}/hqdefault.jpg`** | **HTTP 200** | **HTTP 404** | **高** ✅ |
| **③ embed videoId** | **`youtube.com/embed/{VID}` 中的 videoId 次數** | **≥2 次** | **1 次（僅 URL）** | **高** ✅ |

⚠️ **oembed 重要限制（實測發現）：**
oembed 的 `type` 欄位**一律回傳 `video`**，無法區分即時串流 vs 一般影片 vs 縮時攝影。不要用 `type` 判斷是否為直播 — 應以標題關鍵詞為準。

⚠️ **已修復的偽陽性問題：**
舊版做法（關鍵詞 grep `unavailable`/`private`/`無法觀看`）會在有效影片上產生誤判，因為 CSS 類別 `.player-unavailable` 和 JS 設定變數（如 `html5_hide_unavailable_subtitles_button`）中**永遠**包含這些字眼，與影片是否有效無關。改用 **videoId 出現次數**後已解決此問題，實測 0 偽陽性。

**驗證失敗處理：**
若某 ID 判定失效 → 從文章中移除該 ID → 搜尋替代來源：
```bash
# 優先搜尋官方頻道 /streams 頁面
curl -sL "https://www.youtube.com/@trimtnsa/streams" | grep -oP 'watch\?v=[\w-]{11}' | sort -u
```
當某景區完全無替代來源時，在文章中註明「目前無可用即時影像」，**不要偽造或留空**。

---

## 參考檔案
- `references/obsidian-archive.md` — HTML/RSS → Markdown 轉換工作流
- `references/cctv-taiwan-scenic.md` — 台灣景區 CCTV 即時影像嵌入指南（YouTube ID 對照表、掃描腳本）
- `references/daxi-old-street.md` — 大溪老街關鍵知識庫（建築風格正解、必吃/必遊清單、交通要點）
- `references/tourism-bureau-attractions-api.md` — 交通部觀光署景點開放資料 API 文件（欄位說明、分類對照表、縣市分布）
- `references/tourism-category-codes.md` — 四資料集完整分類代碼對照（景點 28 類 + 餐飲 28 類 + 旅宿 5 類 + 活動 30 類）
- `scripts/verify-youtube-ids.sh` — 批量 YouTube ID 驗證腳本（三層：oembed + 縮圖 + embed videoId 計數）

## 已知陷阱
1. **查證底線陷阱** — 每項資訊至少查證 1–2 個來源，但最多 3 個即收斂。不可因查證而拖延寫作進度。使用者喊停時必須立即停。
2. **硬性價格禁令 ⚠️** — 所有旅遊美食文一律禁止價格資訊（NT$、元、$/塊、價位、銅板價、佛心價、實惠等暗示皆不可出現）。不論使用者有沒有提，預設就不寫。若使用者主動說「寫價格」，才例外恢復。
3. **HTTP 200 ≠ 影片有效 ⚠️** — YouTube oembed 和 embed 頁面對已刪除/私人/不存在的影片仍回 HTTP 200。不能只看狀態碼，**必須檢查 videoId 在 embed 頁面的出現次數**（有效影片 ≥2 次，不存在 =1 次）及**縮圖可用性**（200=有效，404=失效）。這兩個訊號實測 0 偽陽性。
4. **直接 MX 投遞 Mail2Blogger（port 25）：純文字 OK，大圖被吞** — 純文字信件經直接 MX 寄送可達 Blogger 草稿匣，無需任何認證。含 base64 大圖（>2MB）的 HTML 信件 Google 會收下（250 OK）後無聲丟棄。
5. **設定檔路徑不可用 `~`** — Docker 環境中 HOME=/root 不可寫。所有 Blogger 設定檔固定存放在 `/opt/data/.config/blogger/`。
6. **Obsidian 權限問題** — 手機端 uid 1000 vs Docker hermes 使用者，歸檔後務必 `chmod -R 777`。
7. **XDG_CACHE_HOME uv 緩存** — Docker 環境中 `/root/.cache/uv` 不可寫。執行 `uv run` 前必須先設定 `export XDG_CACHE_HOME=/opt/data/.cache`，否則 uv 會因權限錯誤而失敗。
8. **建築/歷史描述陷阱 ⚠️** — 熱門景點的常見旅遊敘述（如「巴洛克建築」、「百年老店」）不一定正確。涉及建築風格、歷史背景、年份數據時，必須查證至少 1 個專業來源（學者論文、官方資料、專家報導），不可僅引用一般旅遊部落格。實例：大溪老街常被旅遊網站稱為「巴洛克建築」，但成大建築系教授指出其正確分類為「西洋歷史式樣（辰野金吾式樣）」。
9. **在地限定特產陷阱 ⚠️** — 每個景點有其獨特限定伴手禮（如大溪的月光餅、萬巒的豬腳），搜尋時應主動以「[地名] 限定」、「[地名] 特色小吃」、「[地名] 必買伴手禮」等關鍵詞查詢，勿僅憑常見印象涵蓋。大溪最常見的被忽略特產就是月光餅（地瓜餅）。
