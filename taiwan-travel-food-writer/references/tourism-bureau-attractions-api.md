# 交通部觀光署 — 景點開放資料 API

> 最後更新：2026-07-17 · 資料版本：V2.1

## 資料集

- **正式名稱：** 景點 - 觀光資訊資料庫
- **提供機關：** 交通部觀光署
- **開放平臺：** <https://data.gov.tw/dataset/7777>
- **更新頻率：** 每日
- **授權：** 政府資料開放授權條款-第1版（免費商用）
- **聯絡人：** 邱小姐 (02)2349-1500#8763

## 下載網址

```
https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Attraction-json.zip
```

ZIP 內容：

| 檔案 | 說明 | 約略大小 |
|------|------|:--------:|
| `AttractionList.json` | 景點基本資料 | ~16MB |
| `AttractionServiceTimeList.json` | 營運時間 | ~64KB |
| `AttractionFeeList.json` | 收費資料 | ~35KB |
| `manifest.csv` | 資料集清單 | ~300B |
| `schema-*.csv` | 欄位定義 | 各 ~100B |

## 讀取方式

```python
import json, zipfile

# 解壓
with zipfile.ZipFile('/tmp/attractions.zip', 'r') as z:
    z.extractall('/tmp/attractions_data')

# 讀取（注意 utf-8-sig BOM）
with open('/tmp/attractions_data/AttractionList.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

attrs = data['Attractions']  # list[dict], 6,095 items
```

## JSON 結構（根層級）

```json
{
  "UpdateTime": "2026-07-17T02:31:18+08:00",
  "UpdateInterval": 86400,
  "Language": "Zh_tw",
  "ProviderID": "A15010000H",
  "Attractions": [ ... ]  // 6,095 items
}
```

## 每筆景點欄位說明

| 欄位 | 類型 | 範例 | 說明 |
|------|------|------|------|
| `AttractionID` | string | `Attraction_345040000G_000001` | 唯一識別碼 |
| `AttractionName` | string | 太平山國家森林遊樂區 | **景點名稱** |
| `AlternateNames` | array | [] | 別名 |
| `Description` | string | 蹦蹦車、溫泉、高山湖泊... | **描述（50–900 字）** |
| `PositionLat` | float | 24.5574 | **緯度** |
| `PositionLon` | float | 121.4995 | **經度** |
| `Geometry` | null | — | 幾何圖形(未使用) |
| `AttractionClasses` | array[int] | [16] | **分類代碼陣列** |
| `PostalAddress` | object | `{City, Town, StreetAddress, ...}` | **地址** |
| `Telephones` | array[{Tel}] | `[{"Tel": "(03)9770766"}]` | 電話 |
| `Images` | array[{Name,URL}] | `[{Name: "翠峰湖日出", URL: "https://..."}]` | **圖片陣列(≤16)** |
| `Organizations` | array | [] | 管理單位 |
| `ServiceTimeInfo` | string | `06:00–20:00` | **開放時間** |
| `TrafficInfo` | string | 國道5號→省道台7線... | **交通方式** |
| `ParkingInfo` | string | 小型車100元 | 停車資訊 |
| `Facilities` | array | [] | 設施 |
| `ServiceStatus` | int | 1 | 營運狀態(1=正常) |
| `IsPublicAccess` | int | 1 | 對外開放 |
| `IsAccessibleForFree` | int | 0 | 免費參觀 |
| `FeeInfo` | string | — | 收費說明 |
| `PaymentMethods` | array | [] | 付款方式 |
| `LocatedCities` | array | [] | 所在鄉鎮 |
| `WebsiteURL` | string | `https://recreation.forest.gov.tw/...` | **官方網站** |
| `ReservationURLs` | array[url] | [...] | 預約網址 |
| `MapURLs` | array[url] | [] | 地圖網址 |
| `SameAsURLs` | array[url] | [] | 相同來源 |
| `SocialMediaURLs` | array[{Name,URL}] | `[{Name: "太平山", URL: "https://facebook.com/..."}]` | 社群媒體 |
| `VisitDuration` | null | — | 建議停留時間 |
| `AssetsClass` | null | — | 資產分類 |
| `SubAttractions` | array | [] | 子景點 |
| `PartOfAttraction` | null | — | 所屬父景點 |
| `Tags` | array[string] | ["賞楓","溫泉","雲海"] | **標籤** |
| `Remarks` | string | — | 備註 |
| `UpdateTime` | string | `2026-07-17T00:20:08+08:00` | 資料更新時間 |

## 分類代碼對照表

> 此分類為交通部觀光署定義的 28 類景點類型。

| ID | 分類名稱 | 數量 | IG 監控適合度 | 說明 |
|:--:|---------|:----:|:------------:|------|
| 1 | 文化類 | 1,783 | ◐ | 博物館、文化中心、藝文園區 |
| 2 | 生態類 | 778 | ✅ | 生態保護區、溼地、賞鳥 |
| 3 | 文化資產類 | 775 | ◐ | 古蹟、歷史建築 |
| 4 | 宗教廟宇類 | 563 | ◐ | 寺廟、教堂、宗教聖地 |
| 5 | 藝術類 | 374 | ✅ | 公共藝術、文創園區 |
| 6 | 商圈商店類 | 260 | ✅ | 老街、夜市、商圈 |
| 7 | 國家公園類 | 39 | ✅ | (內政部國家公園署轄) |
| 8 | 國家風景區類 | 377 | ✅ | (交通部觀光署轄) |
| 9 | 休閒農業類 | 273 | ✅ | 休閒農場、觀光果園 |
| 10 | 溫泉類 | 46 | ✅ | 溫泉區、泡湯 |
| 11 | 自然風景類 | 866 | ✅ | 山岳、瀑布、湖泊、海岸 |
| 12 | 遊憩類 | 1,508 | ✅ | 公園、景觀台、步道 |
| 13 | 體育健身類 | 271 | ✅ | 運動中心、球場、自行車道 |
| 14 | 觀光工廠類 | 277 | ✅ | 工廠參觀、DIY 體驗 |
| 15 | 都會公園類 | 171 | ✅ | 城市公園、綠地 |
| 16 | 森林遊樂區類 | 47 | ✅ | 國家森林遊樂區(林業署) |
| 17 | 平地森林園區類 | 13 | ✅ | 平地森林(林業署) |
| 18 | 國家自然公園類 | 499 | ✅ | (內政部國家公園署轄) |
| 19 | 公園綠地類 | 178 | ✅ | 鄰里公園、社區公園 |
| 20 | 觀光遊樂業類 | 9 | ◐ | 主題樂園、遊樂園 |
| 21 | 原住民文化類 | 29 | ✅ | 部落、原民文化園區 |
| 22 | 客家文化類 | 18 | ✅ | 客庄、客家文化園區 |
| 23 | 交通場站類 | 61 | ◐ | 車站、機場、港口 |
| 24 | 水域環境類 | 96 | ✅ | 水庫、港口、親水設施 |
| 25 | 藝文場館類 | 260 | ✅ | 表演廳、美術館 |
| 26 | 生態場館類 | 22 | ✅ | 生態館、自然教育中心 |
| 27 | 娛樂場館類 | 64 | ✅ | 電影院、KTV、遊戲場 |
| 254 | 其他 | 292 | ◐ | 未分類或特殊類型 |

**IG 監控適合度：** ✅ 推薦（話題性高、適合拍照分享） · ◐ 依需求（特定主題可選）

## 縣市分布

| 縣市 | 數量 | 備註 |
|------|:----:|------|
| 新北市 | 660 | |
| 臺南市 | 546 | |
| 新竹縣 | 478 | |
| 臺中市 | 459 | |
| 臺北市 | 434 | |
| 雲林縣 | 371 | 原 28 筆缺 ✅ |
| 高雄市 | 368 | |
| 彰化縣 | 308 | 原 28 筆缺 ✅ |
| 臺東縣 | 287 | |
| 桃園市 | 281 | |
| 嘉義縣 | 250 | |
| 花蓮縣 | 242 | |
| 金門縣 | 224 | |
| 苗栗縣 | 215 | 原 28 筆缺 ✅ |
| 宜蘭縣 | 174 | 原 28 筆缺 ✅ |
| 南投縣 | 166 | |
| 澎湖縣 | 145 | 原 28 筆缺 ✅ |
| 基隆市 | 123 | |
| 屏東縣 | 122 | |
| 連江縣 | 85 | |
| 嘉義市 | 82 | |
| 新竹市 | 75 | |

## 結合 IG Location 監控

官方景點資料可作為 IG 景點監控的種子清單：

1. **下載 AttractionList.json** — 取得全台 6,095 筆景點
2. **過濾分類** — 選取適合 IG 的類型（自然風景、遊憩、森林遊樂區等）
3. **依縣市分群** — 按 `PostalAddress.City` 分組
4. **用 anysearch 配對 IG Location ID**
   ```bash
   python3 /opt/data/skills/web-search/anysearch/scripts/anysearch_cli.py \
     search "太平山國家森林遊樂區 instagram location"
   ```
5. **存入 SQLite** — 將配對結果存入 `ig_locations.db`

## TDX Open API（替代方案）

交通部另有 TDX 標準化平台，提供 RESTful API（需免費註冊 Key）：

- **入口：** <https://ptx.transportdata.tw/>
- **版本：** v2/Tourism
- **特色：** 支援縣市篩選、坐標範圍查詢、即時資料

一般用途建議直接下載 JSON ZIP 即可，無需註冊 TDX。

## 其他相關資料集

| 資料集 | data.gov.tw 連結 | 說明 |
|--------|:-----------------:|------|
| 餐飲 | `/dataset/7779` | 餐廳、美食（3,000+ 筆） |
| 旅宿 | `/dataset/7778` | 旅館、民宿（10,000+ 筆） |
| 活動 | `/dataset/7776` | 節慶、展覽、活動（2,000+ 筆） |

## 已知問題

- **編碼：** JSON 有 UTF-8 BOM，讀取須用 `utf-8-sig`
- **AttractionClasses 為數字代碼：** 非文字，須對照本文件的分類表
- **圖片可能過時：** 部分圖片由管理處上傳多年未更新
- **Description 長短不一：** 從 50 字到 900 字都有，短篇需額外補充
- **部分欄位為空：** `FeeInfo`、`ServiceTimeInfo` 等欄位可能為空字串
