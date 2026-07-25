---
name: blog-trending-sop
description: "每日台灣熱門景點部落格 SOP — Google Trends + 新聞媒體交叉比對選題，blogref + anysearch 查證，產文存 Obsidian + Mail2Blogger 投遞。"
version: 1.1.0
author: Hermes Agent
platforms: [linux]
tags: [blog, trends, google-trends, taiwan, travel, sop]
---

# 每日熱門景點部落格 SOP（進階版）

## 概述
整合 **Google Trends** + **新聞媒體報導** + **觀光署開放資料**，每日產出一篇時事性台灣旅遊部落格文章，存入 Obsidian vault 並投遞 Blogger 草稿。

## 觸發條件
- 使用者說「寫部落格」「進階版」「每日熱門景點」
- Cron job 每日定時觸發

---

## Step 1：抓取 Google Trends 台灣旅遊熱搜（30 秒）

### 目標
取得當日台灣「旅遊與運輸工具」分類（cat=71）的即時熱搜關鍵字。

### 方法
```
# 提取 Google Trends 台灣旅遊分類頁面
anysearch extract → https://trends.google.com.tw/trending?geo=TW&cat=71
```

### 輸出
- 熱搜關鍵字列表（名稱 + 搜尋量 + 趨勢狀態）
- 過濾出**旅遊/景點/美食/活動**相關項目
- 標記「活躍」（trending_up）vs「持續時間」（timelapse）

### 選題原則
1. **優先：** 當季景點 + 時事性（煙火節、花季、蝶季、新開幕等）
2. **次選：** 美食新店、老街活動、親子景點
3. **避免：** 純政治/體育/娛樂新聞（Google Trends 混雜非旅遊項目）

### 交叉比對
```
# 同時搜尋新聞報導驗證熱度
anysearch search → "台灣 [關鍵字] 景點 旅遊 2026年7月"
```
- 至少 2 家媒體報導 = 確認熱度
- 無新聞佐證 = 降低優先級

### Step 1 判定結果
- **找到旅遊主題** → 進入 Step 2 正常流程
- **無旅遊主題** → 進入 Step 1b Fallback 機制

---

## Step 1b：Fallback 主題庫選題（當 Google Trends 無旅遊主題時）

### 判定標準
以下任一條件成立即觸發 fallback：
- Google Trends 前 25 名無旅遊/景點/美食/活動相關項目
- 有旅遊項目但無新聞佐證（熱度不足）
- 颱風/天災期間旅遊類搜尋異常低

### Fallback 主題庫（依季節自動選擇）

#### 🌸 春季（3-5 月）
| 主題 | 類型 | 說明 |
|------|------|------|
| 陽明山海芋季 | 花季 | 竹子湖海芋田體驗採花 |
| 武陵農場櫻花季 | 花季 | 2-3月為主，可延伸到4月 |
| 台中賞螢 | 生態 | 大坑、松園步道 |
| 桃園彩色海芋季 | 花季 | 大園埔心 |

#### ☀️ 夏季（6-8 月）
| 主題 | 類型 | 說明 |
|------|------|------|
| 墾丁戲水 | 海邊 | 船帆石、後壁湖、白沙灣 |
| 鹿谷紫斑蝶 | 生態 | 7-10月蝶季（今年大爆發） |
| 日月潭水域活動 | 水上 | SUP、划船、自行車 |
| 東石海之夏 | 活動 | 7月底煙火秀 |
| 清境高山花卉 | 花季 | 合歡山金針花7-8月 |

#### 🍁 秋季（9-11 月）
| 主題 | 類型 | 說明 |
|------|------|------|
| 奧萬大賞楓 | 楓葉 | 11-12月 |
| 太魯閣峽谷 | 自然 | 秋高氣爽登山 |
| 梅嶺賞梅 | 花季 | 12月起 |
| 高美濕地夕陽 | 自然 | 秋季候鳥過境 |

#### ❄️ 冬季（12-2 月）
| 主題 | 類型 | 說明 |
|------|------|------|
| 關子嶺溫泉 | 溫泉 | 冬季首選 |
| 北投溫泉 | 溫泉 | 城區泡湯 |
| 台南鹽水蜂炮 | 活動 | 元宵節限定 |
| 平溪天燈 | 活動 | 春節期間 |

### Fallback 選題流程
1. 取得今日日期 → 判斷當前季節
2. 從對應季節主題庫隨機選 1 個（優先選未寫過的）
3. 用 anysearch 搜尋「[主題] 最新 2026」確認是否有新動態
4. 有新動態 → 寫該主題（搭配最新資訊）
5. 無新動態 → 從庫中再選下一個，最多嘗試 3 個
6. 3 個都無新動態 → **當天不產文**，回報「今日無適合主題，跳過」

### 避免重複
- 每次寫完文章後，將主題標記到 `/opt/data/obsidian-vault/17uu/_used_topics.md`
- Fallback 選題時先讀取此檔，排除已用過的主題（近 30 天內）
- 每月 1 日自動清除超過 30 天的記錄

---

## Step 2：查證景點資料（1-2 分鐘）

### 2a. blogref 查詢（官方觀光署資料）
```bash
# 搜尋景點
bash /opt/data/scripts/blogref search [景點名] --city [縣市]

# 查該縣市所有景點
bash /opt/data/scripts/blogref attractions --city [縣市]

# 查周邊美食
bash /opt/data/scripts/blogref restaurants --city [縣市]
```
- 有資料 → 直接引用 Description、TrafficInfo、ServiceTimeInfo
- 無資料 → 走 2b

### 2b. anysearch 查證（網路資料）
搜尋以下資訊，每項至少 1-2 個來源交叉比對：

| 資料 | 搜尋關鍵字範例 |
|------|----------------|
| 地址 | `[景點名] 地址` |
| 營業時間 | `[景點名] 營業時間 開放時間` |
| 交通方式 | `[景點名] 交通 怎麼去 停車` |
| 門票/入園資訊 | `[景點名] 門票 票價 入園` |
| 特色/亮點 | `[景點名] 推薦 必看 特色` |
| 周邊美食 | `[地名] 美食 推薦 必吃` |

### 2c. Google Maps 連結
所有地址一律轉為 Google Maps 格式：
```
**Google Maps：** [景點名稱](https://maps.google.com/?q=完整地址)
```

### 查證上限
- 每項最多比對 **3 個來源**即收斂
- 使用者喊停 → 立即停止搜尋，用手邊資料寫

---

## Step 3：撰寫文章（2-3 分鐘）

### 文章結構模板

```markdown
# [景點名稱] — [一句話特色標題]

## 📍 景點介紹
（200-300 字，含地理位置、特色、為何現在適合去）

## 🚗 交通方式
（自行開車路線 + 大眾運輸 + 停車資訊）

## ⏰ 營業資訊
（開放時間、門票/入園方式、注意事項）

## 📸 景點推薦
### 1️⃣ [特色一]
### 2️⃣ [特色二]
### 3️⃣ [特色三]
（每個 100-150 字，含具體體驗描述）

## 🍜 周邊美食
（1-2 間推薦餐廳，含名稱、特色、必點）

## 💡 小提醒
（注意事項、最佳時段、季節性建議）

## 🔗 延伸閱讀
（Google Maps 連結）
```

### 硬性規則
1. **❌ 禁止價格資訊** — 不寫 NT$、元、$/塊、銅板價、佛心價
2. **✅ Google Maps 連結** — 一律用 `[名稱](https://maps.google.com/?q=地址)` 格式
3. **✅ 查證引用** — 文末加註資料來源
4. **✅ 時事切入** — 開頭用當季/時事吸引讀者

---

## Step 4：儲存文章（10 秒）

```bash
# 存到 Obsidian vault（blogger_send.sh 直接讀取）
/opt/data/obsidian-vault/17uu/[景點名]_[主題]_[YYYY-MM-DD].md

# 權限修正（手機 Sync 需要）
chmod -R 777 /opt/data/obsidian-vault/17uu/
```

---

## Step 5：投遞 Blogger 草稿（10 秒）

```bash
# 一鍵投遞（不帶圖片，直接 MX port 25）
export XDG_CACHE_HOME=/opt/data/.cache
uv run python3 /opt/data/scripts/blogger_direct.py \
  /opt/data/obsidian-vault/17uu/[文章檔名].md --no-images
```

### 驗證
- 腳本回傳 `✅ 信件已送出`
- 到 https://draft.blogger.com 確認草稿

---

## Step 6：回報使用者（最終回覆）

回傳格式：
```
📝 文章：[標題]
📊 選題來源：Google Trends [關鍵字] + [N]家新聞媒體
🔍 查證：blogref [有/無] + anysearch [N]項
✅ 存入：Obsidian vault 17uu/
✅ 投遞：Blogger 草稿已送出
```

---

## 完整流程圖

```
Google Trends (cat=71)
    ↓ 過濾旅遊相關
    ↓
    ├─ 有旅遊主題 → 新聞媒體交叉比對 → 確認熱度 → 選定主題
    │
    └─ 無旅遊主題 → Step 1b Fallback 主題庫
                      ├─ 季節主題庫選 3 個
                      ├─ anysearch 確認最新動態
                      ├─ 有新動態 → 寫該主題
                      └─ 3 個都無 → 當天不產文，回報「跳過」
    ↓
blogref 查官方資料 (景點/美食/活動)
    ↓
anysearch 補充查證 (地址/時間/交通/特色)
    ↓
撰寫文章 (模板 + 硬性規則)
    ↓
存入 Obsidian vault 17uu/
    ↓
chmod 777
    ↓
Mail2Blogger MX 投遞 (blogger_direct.py)
    ↓
記錄已用主題到 _used_topics.md
    ↓
回報使用者
```

---

## 已知陷阱

1. **Google Trends 混雜非旅遊項目** — cat=71 雖已篩選「旅遊與運輸工具」，仍可能混入政治人物、股票等。需人工過濾。
2. **blogref 無收錄的新景點** — 部分小型或新開景點不在觀光署資料庫，需完全依賴 anysearch 查證。
3. **價格禁令不可違反** — 即使查到票價也不寫入文章，除非使用者明確說「寫價格」。
4. **MX 投遞不含圖片** — 使用 `--no-images`，大圖 HTML 會被 Google 丟棄。
5. **Obsidian 權限** — Docker hermes 使用者 vs 手機 uid 1000，歸檔後務必 chmod 777。
6. **Google Trends 即時性** — 熱搜每小時變動，抓取時間影響選題。建議固定在上午 9-10 點執行。
7. **Fallback 主題庫需維護** — 每季手動更新一次，加入新景點、移除已下架景點。主題庫在 SKILL.md 的 Step 1b 區塊。
8. **主題重複** — `_used_topics.md` 記錄近 30 天已用主題，避免同一个月寫兩篇相同景點。
