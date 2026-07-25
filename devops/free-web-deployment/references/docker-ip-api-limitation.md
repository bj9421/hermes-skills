# Docker Container 外部 API 存取限制

## 問題

Flask 後端在 Docker 容器內時，**無法從容器內部呼叫外部 IP 反查 API**（如 ip-api.com、ipinfo.io）。

## 原因

- Docker bridge network 的 NAT 轉譯可能阻擋部分外部連線
- 某些 API 服務商拒絕來自資料中心 IP range 的請求
- Hermes Agent 容器可能有額外的網路隔離設定

## 解法

**從前端（瀏覽器）直接呼叫**，而不是從 Flask 後端：

```javascript
// ✅ 正確：前端呼叫（瀏覽器有完整網路存取）
fetch('http://ip-api.com/json/?lang=zh-TW')
    .then(r => r.json())
    .then(data => { /* 使用城市資料 */ });

// ❌ 錯誤：後端呼叫（Docker 容器內可能不通）
# Flask app.py 內
urllib.request.urlopen('http://ip-api.com/json/')  # 可能 timeout 或 connection refused
```

## 備註

- ip-api.com 免費方案：50 req/min，不需要 API key
- 前端呼叫使用 `http://` 即可（不需要 HTTPS）
- 如果前端也在 HTTPS 頁面，改用 `https://` 或改用其他支援 HTTPS 的 IP 查詢服務
