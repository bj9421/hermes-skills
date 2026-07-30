# Tailscale Serve 部署須知

> 將 Flask + HTMX 內部工具透過 Tailscale 安全暴露。

## 基本指令

```bash
# 掛在 root（HTMX PWA 最推薦）
tailscale serve --bg --https 443 http://localhost:5001

# 不同 port
tailscale serve --bg --https 8443 http://localhost:9119

# 管理
tailscale serve status
tailscale serve --https=443 off
```

## 重要教訓

### 路徑選擇：root 優先

HTMX 應用大量使用絕對 `/` 路徑（`/api/...`、`/static/...`）。
若掛在子路徑（`/bm`），所有 `/` 前綴路徑會斷掉 → 需全部改成相對路徑。

**結論**：HTMX 應用一律掛 proxy root `/`。

### ERR_SSL_PROTOCOL_ERROR

- **原因**：瀏覽器不在 tailnet 內，直接透過公開 DNS 連線
- Tailscale serve 只監聽 `100.x.x.x:443` 不監聽 `0.0.0.0:443`
- 裝置需安裝 Tailscale App 並登入同帳號

### Backend URL 用 http://

```bash
# 正確
tailscale serve --bg --https 443 http://localhost:5001
# 錯誤 — SSL 由 Tailscale 終止，不要用 https://
```

### 多路徑嘗試（不適合 HTMX）

```bash
# 這個語法正確但不建議給 HTMX 用
tailscale serve --bg --https=443 --set-path=/bm localhost:5001
```
