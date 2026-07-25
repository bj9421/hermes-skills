---
name: free-web-deployment
description: "Deploy Flask/Python web apps on free hosting (Render, PythonAnywhere, Vercel). Covers DB optimization, repo setup, Procfile, and zero-cost deployment."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
tags: [deploy, flask, render, free-hosting, sqlite, web-app]
---

# 免費網頁部署技能 (Free Web Deployment)

## 當需要使用此技能時

- 使用者要建一個 Flask/Python Web 應用但不想花錢部署
- 需要把 SQLite 資料庫應用部署到雲端免費方案
- 要在 Blogger 側邊欄嵌入外部查詢頁面
- 樹莓派上的資料需要透過 Web 介面展示

## 部署方案比較

| 方案 | 費用 | Flask 支援 | SQLite | HTTPS | 限制 | 推薦度 |
|------|------|-----------|--------|-------|------|--------|
| **Render** | 免費 | ✅ 原生 | ✅ | ✅ 自動 | 15 分鐘無活動休眠、512 MB RAM | ⭐⭐⭐⭐⭐ |
| **PythonAnywhere** | 免費 | ✅ | ✅ | ✅ (付費域名) | 1 個 app、出站網路限制 | ⭐⭐⭐ |
| **Vercel** | 免費 | ⚠️ serverless | ❌ | ✅ 自動 | 執行時間限制 | ⭐⭐ |
| **GitHub Pages** | 免費 | ❌ | ❌ | ✅ 自動 | 僅靜態 | ⭐ |
| **樹莓派本地** | 免費 | ✅ | ✅ | ❌ | 需開 port、IP 可能變動 | ⭐⭐⭐ |

**預設推薦：Render** — 免費方案夠用，GitHub 串接自動部署，5 分鐘搞定。

## 工作流程

### Phase 1: 資料庫優化（必要步驟）

大型 SQLite 資料庫（>50 MB）需要先精簡再部署。

#### 1.1 分析資料庫結構

```python
import sqlite3
db = sqlite3.connect('data.db')
c = db.cursor()

# 檢查表格與筆數
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
for t in c.fetchall():
    c.execute(f"SELECT COUNT(*) FROM {t[0]}")
    print(f"{t[0]}: {c.fetchone()[0]} 筆")

# 檢查大欄位
c.execute("SELECT AVG(LENGTH(data_json)), SUM(LENGTH(data_json)) FROM table_name")
avg, total = c.fetchone()
print(f"data_json 平均: {avg:.0f} bytes, 總計: {total/1024/1024:.1f} MB")
```

#### 1.2 建立精簡版資料庫

```python
import sqlite3, os

src = sqlite3.connect('data/original.db')
dst = sqlite3.connect('data/lite.db')

c_dst = dst.cursor()
c_dst.execute('''
    CREATE TABLE table_name (
        id TEXT,
        name TEXT,
        city TEXT,
        address TEXT,
        lat REAL,
        lng REAL,
        phone TEXT,
        level TEXT,
        description TEXT
    )
''')

# 只複製必要欄位
src_c = src.cursor()
src_c.execute('SELECT id, name, city, address, lat, lng, phone, level, description FROM table_name')
rows = src_c.fetchall()
c_dst.executemany('INSERT INTO table_name VALUES (?,?,?,?,?,?,?,?,?)', rows)
dst.commit()

# 檢查壓縮率
src_size = os.path.getsize('data/original.db')
dst_size = os.path.getsize('data/lite.db')
print(f'壓縮率: {(1 - dst_size/src_size)*100:.1f}%')
```

**關鍵原則：**
- 只保留前端需要的欄位（名稱、位置、等級、地址、電話、描述）
- 移除 `data_json` 等大欄位（通常佔 20-50% 容量且與表格欄位重複）
- 目標：< 10 MB（Render 免費方案足夠）

### Phase 2: Flask 專案結構

```
project/
├── app.py                  # Flask 後端（路由 + API）
├── requirements.txt        # 依賴（flask, gunicorn）
├── Procfile                # Render 啟動指令（web: gunicorn app:app）
├── README.md               # 專案說明
├── .gitignore              # 忽略 venv、cache
├── templates/
│   └── index.html          # 主頁面
├── static/
│   ├── css/
│   │   └── style.css       # 樣式
│   └── js/
│       └── app.js          # 前端邏輯
└── data/
    └── data_lite.db        # 精簡版資料庫
```

#### 2.1 Procfile（Render 專用）

```
web: gunicorn app:app
```

#### 2.2 requirements.txt

```
flask==3.1.0
gunicorn==23.0.0
```

#### 2.3 .gitignore

```
__pycache__/
*.py[cod]
venv/
.env/
.DS_Store
```

### Phase 3: Flask 後端模板

```python
import sqlite3, os
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'lite.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/hotels')
def search_hotels():
    city = request.args.get('city', '').strip()
    keyword = request.args.get('keyword', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # 建構動態查詢
    conditions = []
    params = []
    if city:
        conditions.append("city = ?")
        params.append(city)
    if keyword:
        conditions.append("(name LIKE ? OR description LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) as cnt FROM table {where}", params).fetchone()['cnt']
    
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM table {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    db.close()
    
    return jsonify({
        'data': [{'id': r['id'], 'name': r['name']} for r in rows],
        'pagination': {'page': page, 'total': total, 'total_pages': max(1, (total + per_page - 1) // per_page)}
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

### Phase 4: 前端模板（Leaflet 地圖 + 篩選）

使用 Leaflet + OpenStreetMap（免費，免 API Key）：

```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map = L.map('map').setView([23.7, 120.96], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
// ... 載入 API 資料，用 circleMarker 標註
</script>
```

**設計原則：**
- 白底、淺灰邊框、無多餘裝飾（簡潔風格）
- 地圖佔 70%、列表佔 30%
- 手機版自動切換全屏地圖 + 底部抽屐列表

### Phase 5: Render 部署

#### 5.1 註冊與設定

**⚠️ 2026-07 更新：Render 免費方案現在需要綁定信用卡**

- 透過 API 創建服務會回傳 402（即使選 free plan）
- 已綁定信用卡的帳戶才能用 API 創建
- 未綁定需走 Dashboard 手動創建

手動創建步驟：
1. 前往 https://dashboard.render.com 登入
2. New → Web Service
3. Connect GitHub repo
4. 設定：
   - **Name**: 自訂
   - **Region**: Automatic（或選 taiwan）
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free

API 創建（需已綁定信用卡）：
- 完整 payload 結構見 `references/render-api-v1-service-creation.md`
- 關鍵：`type` 用 `web_service`（不是 `web`），`ownerId` 格式 `tea-xxx`
- `serviceDetails.envSpecificDetails` 必填 `buildCommand` + `startCommand`

#### 5.2 資料庫處理

SQLite 檔放在 repo 中（因為 Render 免費方案無持久化儲存）。每次更新資料：
1. 在本機精簡資料庫
2. 覆蓋 `data/lite.db`
3. `git add data/lite.db && git commit -m "update db" && git push`

**注意：** Render 免費方案每次部署會重建容器，資料庫狀態不會保留。如果需要在運行時寫入資料庫，需改用 PostgreSQL（Render 提供免費 PostgreSQL trial）。

## 本機測試與除錯

### 在 Docker 容器中安裝 Python 依賴

Docker 容器內常遇到 pip 被 Hermes 的 long-lived process guard 攔截（因為進度條互動式輸出）。解法：

1. **用 `venv` + 專案內 pip**（推薦）：
   ```bash
   cd /path/to/project && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt --quiet
   ```
2. **或用 background terminal**：
   ```bash
   # 用 background=true 啟動 pip install，然後 process(wait) 等它結束
   ```

### Docker 容器內 pip 不可用的解法

有時容器內的 Python 沒有 pip module（`No module named pip`），而 `apt-get install python3-pip` 又沒有 root 權限。解法：

1. **用 Python 內建 venv**（不需要 pip）：
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. 如果連 `python3 -m pip` 都沒有 → 用系統 python3 的 pip（如果有）：
   ```bash
   /usr/bin/python3 -m pip install --break-system-packages flask
   ```
3. **絕對不要**用 `apt-get install python3-pip` 除非有 root 權限。

### 檢查 Flask 是否已在跑

```bash
# 看 port 5000 有沒有被佔用
cat /proc/net/tcp | awk '{print $2}' | grep -i "1388"  # 5000=0x1388
# 或直接
ps aux | grep python | grep -v grep
```

## 常見陷阱

### 陷阱 1: SQLite 資料庫過大導致部署失敗

**症狀：** Render 部署時 timeout 或記憶體不足
**原因：** 原始資料庫 >50 MB（包含重複的 data_json 欄位）
**解法：** 建立精簡版資料庫，只保留必要欄位

### 陷阱 2: Render 免費版休眠

**症狀：** 第一次存取要等 30-50 秒
**原因：** 免費方案 15 分鐘無活動會休眠
**解法：** 對「偶爾查詢」應用無影響；如需即時回應，考慮每月 $7 的 Starter 方案

### 陷阱 3: uv pip install 快取權限問題

**症狀：** `Failed to initialize cache at /root/.cache/uv — Permission denied`
**解法：** 在樹莓派 Docker 容器內使用 `UV_CACHE_DIR=/tmp/.uv-cache uv pip install -r requirements.txt`

### 陷阱 4: 後端有資料但前端拿不到

**症狀：** API 正常但地圖空白
**原因：** API 回傳的欄位名稱與前端 JS 期望的不符
**解法：** 檢查 JSON 結構一致性，特別注意 `lat`/`lng` vs `latitude`/`longitude` 命名差異

### 陷阱 5: 手機版側邊欄高度失控

**症狀：** iframe 嵌入時內容被裁切
**解法：** 使用 `target="_blank"` 在新視窗開啟，而非 iframe 嵌入

## 替代方案：Blogger 側邊欄嵌入

如果不想用獨立頁面，可以在 Blogger 側邊欄放文字連結：

```html
<a href="https://your-app.onrender.com" target="_blank">🏨 住宿查詢</a>
```

使用者點擊後在新視窗開啟完整查詢頁面。

## 雲端免費方案 2026-07 實測更新

### Render 免費方案（2026-07 更新）
- ✅ **完全免信用卡** — 手動 Dashboard 創建即可
- ❌ **API 創建需信用卡** — `POST /v1/services` 回傳 402，新帳號無法用 API 創建
- ⚠️ **SQLite 不持久化** — Free 方案不能掛 Volume，每次休眠/重啟 SQLite 全清空
- ⚠️ **750 小時/月** — 用完整個月停擺，休眠時不計費
- ⚠️ **15 分鐘休眠** — 無流量就睡，冷啟動約 1 分鐘
- ⚠️ **Postgres 免費 30 天過期** — 不是永久免費
- ⚠️ **無 Cron Jobs** — 無法自動回補資料庫
- 💡 **$7/mo Starter** — 才有持久化磁碟 + 不休眠 + Cron

### Railway 免費方案（2026-07 更新）
- 🎁 **Trial：$5 一次性（30 天）** — 免信用卡
- 🆓 **Free Plan：$1/月（不累積）** — 試用期後自動降級
- ⚠️ **$1/月只夠跑極輕量 App** — 沒有餘裕放資料庫
- ⚠️ **無 Cron Jobs（Free Plan）** — 無法自動排程
- ⚠️ **Volume 有費用** — SQLite 放 Volume 會吃掉 $1 額度
- ⚠️ **停擺 30 天後刪除 Volume 資料**

### 結論
| 需求 | Render 免費 | Railway 免費 |
|------|-----------|-------------|
| 免信用卡 | ✅ | ✅ |
| SQLite 持久化 | ❌ | ⚠️ 需付費 Volume |
| Cron 排程 | ❌ | ❌ |
| 長期免費可用 | ⚠️ 需手動重建 DB | ⚠️ $1 不夠 DB+App |
| 推薦度 | ⭐⭐⭐ | ⭐⭐ |

**最佳免費方案：本機跑（RPi）→ 最穩定、零成本、SQLite 持久化。**

## 變更日誌

| 日期 | 變更 |
|------|------|
| 2026-07-18 | 初次建立：從 17uu.tw 住宿查詢專案提取部署流程與技巧 |
| 2026-07-18 | 更新 Render/Railway 免費方案實測結果 — API 需信用卡、SQLite 不持久化、$1/月不夠 |

## 支援檔案

- `templates/render-procfile` — Render Procfile 範本（`web: gunicorn app:app`）
- `references/render-setup-guide.md` — Render 免費方案完整設定步驟與 FAQ
- `references/render-api-v1-service-creation.md` — Render API v1 服務創建正確 payload 結構與常見錯誤（2026-07 更新）
- `references/railway-vs-render-comparison.md` — Railway vs Render 免費方案詳細比較（2026-07）
- `references/iframe-testing.md` — iframe 測試頁面模板與注意事項（2026-07）
