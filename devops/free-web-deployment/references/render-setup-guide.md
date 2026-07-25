# Render 免費方案部署指南

## 帳號註冊
- 網址：https://render.com
- 只需 email，不需信用卡
- 登入後進入 Dashboard

## 建立 Web Service

1. Dashboard → New Web Service → Connect GitHub repo
2. 選擇你的私人倉庫
3. 填寫設定：

| 欄位 | 值 |
|------|-----|
| Name | 你的應用名稱 |
| Region | Automatic（選最近的） |
| Branch | main |
| Root Directory | （留空，除非專案在 subfolder） |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Instance Type | Free |

4. 按下 Create

## 資料庫更新流程

每次 SQLite 資料庫有更新：

```bash
# 1. 在本機建立精簡版
cd /opt/data/projects/your-project
/opt/data/.venv/bin/python3 -c "
import sqlite3, os
src = sqlite3.connect('data/original.db')
dst = sqlite3.connect('data/lite.db')
c = dst.cursor()
c.execute('CREATE TABLE ...')  # 只建必要欄位
# ... 複製資料
dst.commit()
src.close(); dst.close()
"

# 2. 提交並推送
git add data/lite.db
git commit -m "update database"
git push

# 3. Render 自動偵測變更並重新部署
# 查看部署狀態：https://dashboard.render.com
```

## 常見問題

### Q: 部署後頁面 502 Bad Gateway
**A:** 檢查 logs 是否有啟動錯誤。常見原因：
- requirements.txt 缺少依賴
- gunicorn 找不到 app（確認 app.py 中有 `app = Flask(__name__)`）
- 資料庫路徑不對（Render 的 CWD 是 repo 根目錄）

### Q: 資料庫檔案太大
**A:** Render 免費方案 repo 上限 ~500 MB。如果資料庫 >10 MB：
- 考慮只保留最近 N 天的資料
- 或使用外部資料庫（Render 免費 PostgreSQL trial）

### Q: 冷啟動太慢
**A:** 免費方案 15 分鐘無活動會休眠，首次請求需 30-50 秒喚醒。
- 可考慮每月 $7 的 Starter 方案（永不休眠）
- 或在應用中加入健康檢查頁面

## 部署成功驗證

```bash
# 測試首頁
curl -I https://your-app.onrender.com/
# 應返回 200 + HTML

# 測試 API
curl https://your-app.onrender.com/api/endpoint
# 應返回 JSON

# 檢查 logs
# Render Dashboard → Your Service → Logs
```
