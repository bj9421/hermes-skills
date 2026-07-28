---
name: tailscale-termux-proot
title: "Tailscale on Termux（Android 13+ MIUI 雙節點混合架構）"
description: "在單一 Android 手機上同時跑 Android App + Termux CLI 兩個 Tailscale 節點，用 Serve 曝光 Termux 服務，用 App VPN 直連其他 tailnet 節點"
---

# Tailscale on Termux（Android 13+ MIUI 雙節點混合架構）

## 這份文件解決什麼問題

你有一台 Android 手機（Redmi Note 10），上面同時跑：

- **Termux 服務** — Hermes Dashboard（:9229）、CCTV Map（:8767）
- **手機瀏覽器** — 需要連到其他 tailnet 節點（如 dietpi4:9119）

問題：Termux 沒有自己的 tailnet 連線時，這些服務就無法從 tailnet 其他機器存取。
手機瀏覽器需要 VPN 才能連到 tailnet 節點。

**解法：在同一個裝置上跑兩個 Tailscale 客戶端，各司其職。**

## 完整架構圖

```
                     ┌──────────────────────────────────────┐
                     │           Redmi Note 10               │
                     │                                        │
                     │  ┌─────────────────┐                   │
                     │  │  Android App    │  rmn10            │
                     │  │  (VPN tun0)     │  100.108.117.92   │
                     │  │                 │                   │
                     │  │ 手機瀏覽器 ───→ dietpi4:9119 ✅    │
                     │  └─────────────────┘                   │
                     │                                        │
                     │  ┌─────────────────┐                   │
                     │  │  Termux CLI     │  ttha              │
                     │  │  (userspace)    │  100.112.137.111  │
                     │  │  ── proot ──    │                   │
                     │  │                 │  Serve :443 ─→    │
                     │  │  Hermes Gw      │  Dashboard :9229  │
                     │  │  CCTV Map       │  :8767            │
                     │  │  SOCKS5 proxy   │  :1080            │
                     │  └─────────────────┘                   │
                     │                                        │
                     │  ┌─────────────────┐                   │
                     │  │  Python TCP     │  :9119 (fallback) │
                     │  │  Bridge         │  app OFF 時啟用   │
                     │  └─────────────────┘                   │
                     └──────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
               dietpi4:9119          其他 tailnet 節點
               (Hermes Dashboard)   (laptop, server...)
```

### 三個元件各司其職

| 元件 | 節點名 | IP | 角色 |
|------|--------|----|------|
| **Android App (rmn10)** | `rmn10` | `100.108.117.92` | 手機瀏覽器透過 VPN 直連其他 tailnet 節點 |
| **Termux CLI (ttha)** | `ttha` | `100.112.137.111` | 用 `tailscale serve` 把 Termux 服務曝光到 tailnet |
| **SOCKS5 Proxy** | — | `localhost:1080` | Termux 內部連到其他 tailnet 節點的通道 |

## 完整 Port 對照表

| Port | 服務 | 在誰上面 | 從哪裡可達 |
|------|------|----------|-----------|
| `:9229` | Hermes Dashboard | Termux (ttha) | `127.0.0.1:9229`（本地）→ `https://ttha.taile76ad.ts.net/`（serve） |
| `:8767` | CCTV Taiwan Map | Termux (ttha) | `127.0.0.1:8767`（本地）→ 暫未 serve（可加） |
| `:443` | ttha serve HTTPS | Termux (ttha) | 透過 tailnet DNS `ttha.taile76ad.ts.net` |
| `:1080` | SOCKS5 代理 | Termux (ttha) | Termux 內部 `curl --socks5 127.0.0.1:1080` |
| `:9119` | TCP 橋接（dietpi4 代理） | Termux (ttha) | App OFF 時：LAN IP `192.168.1.105:9119` |
| `80` | — | dietpi4 | `100.78.85.64:9119`（透過 rmn10 VPN 直連） |
| `:9119` | Hermes Dashboard | dietpi4 | App ON：`http://100.78.85.64:9119` |

## 安裝步驟（從零開始）

### 前置需求

- Android 13+（MIUI/HyperOS）
- Termux 已安裝
- Tailscale 帳號（https://login.tailscale.com）

### 1. 安裝 bropines tailscale-termux-cli

```bash
curl -fsSL https://raw.githubusercontent.com/bropines/tailscale-termux-cli/main/remote-install.sh | bash
```

### 2. 產生 auth key

前往 https://login.tailscale.com/admin/settings/keys → 產生 **Reusable** auth key。

### 3. 啟動 daemon（透過 proot 繞過 MIUI seccomp）

為什麼需要 proot？Go 1.26 的 `os/exec` 使用 `clone3`/`posix_spawn`，Android 13+ 的 seccomp 會封鎖 `untrusted_app` domain 的這些 syscall。proot 用 ptrace 攔截取代。

```bash
# 關閉 runsv 自動管理
touch $PREFIX/var/service/tailscaled/down
sv down $PREFIX/var/service/tailscaled 2>/dev/null || true
pkill -9 -f "runsv.*tailscale" 2>/dev/null || true
pkill -9 tailscaled 2>/dev/null || true
sleep 1
rm -f ~/.tailscale/tailscaled.sock

# 在 proot 下啟動（ptrace 攔截讓 os/exec 正常運作）
proot -b /proc -b /sys tailscaled \
    --statedir="$HOME/.tailscale" \
    --socket="$HOME/.tailscale/tailscaled.sock" \
    --tun=userspace-networking \
    --socks5-server=localhost:1080
```

### 4. 認證（方式 A：不須 Auth Key）✅ 最簡單

在手機瀏覽器完成登入，適合一次性設定或 key 已過期時：

```bash
tailscale --socket="$HOME/.tailscale/tailscaled.sock" up
```

執行後終端機會印出一個連結：

```
https://login.tailscale.com/a/XXXXXXXXX
```

用手機瀏覽器打開該連結 → 登入 Tailscale 帳號 → 授權完成。**不需產生 auth key。**

### 5. 認證（方式 B：Auth Key — 適合自動化腳本）

如果需要讓 haup.sh 自動認證（無頭模式），用 auth key：

```bash
tailscale --socket="$HOME/.tailscale/tailscaled.sock" up --auth-key=tskey-auth-xxxxx
```

### 5. 啟用 Serve（讓 Termux 服務可從 tailnet 存取）

第一次執行時會出現啟用連結，必須在瀏覽器打開授權：

```bash
# 先跑一次，取得啟用連結
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --bg 9229
# → "Serve is not enabled on your tailnet. To enable, visit:"
# → https://login.tailscale.com/f/serve?node=nqnKEhyhei11CNTRL

# （去瀏覽器點開連結授權後）再跑一次就生效
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --bg 9229
# → https://ttha.taile76ad.ts.net/ → proxy http://127.0.0.1:9229
```

### 6. 安裝 Android Tailscale App

Google Play 安裝 `Tailscale`，登入同一個帳號。
Android 端節點名自動為 `rmn10`，IP `100.108.117.92`。

## 日常操作

### 正常模式（App VPN ON）

這是預設的日常使用方式。

```
手機操作：
  1. 打開 Tailscale App → 確認 VPN 連線（狀態列出現 VPN 圖示）
  2. 打開瀏覽器 → http://100.78.85.64:9119 → 看到 Hermes 登入畫面 ✅

Termux 檢查：
  tmux ls               → 確認 tailscale session 在跑
  curl --socks5 127.0.0.1:1080 http://100.78.85.64:9119/  → SOCKS5 測試
```

### 備援模式（App VPN OFF）

當 Android App 關閉時，手機瀏覽器無法連到 `100.x.x.x` IP。
用 ttha 的 TCP 橋接把 dietpi4 代理到 LAN IP：

```bash
# 啟動 TCP 橋接（ttha 上執行）
python3 ~/scripts/tailscale-socks-proxy.py 9119 100.78.85.64 9119

# 手機瀏覽器改連 LAN IP
# http://192.168.1.105:9119
```

殺掉橋接：`pkill -f "tailscale-socks-proxy"` 或 Ctrl-C。

⚠️ **socat 不能用** — Tailscale 的 SOCKS5 server 不吃 SOCKS4A，只能用這個 Python 腳本。
⚠️ **TIME_WAIT** — 關掉 proxy 後 30 秒內重開同 port 會 fail，等一下或用不同 port。

## haup.sh 整合（自動啟動）

`~/scripts/haup.sh` 管理所有 tmux session。以下是完整的 tailscale 區塊：

```bash
# tailscale daemon（proot + tailscaled）
if pgrep -f "proot.*tailscaled" >/dev/null 2>&1; then
    echo "⚠️  Tailscale daemon 已在執行"
else
    touch $PREFIX/var/service/tailscaled/down 2>/dev/null || true
    sv down $PREFIX/var/service/tailscaled 2>/dev/null || true
    pkill -9 -f "runsv.*tailscale" 2>/dev/null || true
    pkill -9 tailscaled 2>/dev/null || true
    sleep 1
    rm -f ~/.tailscale/tailscaled.sock

    tmux new-session -d -s tailscale \
      "proot -b /proc -b /sys tailscaled \
          --statedir=\"$HOME/.tailscale\" \
          --socket=\"$HOME/.tailscale/tailscaled.sock\" \
          --tun=userspace-networking \
          --socks5-server=localhost:1080"
fi
```

haup.sh 完整啟動順序：
1. `tailscale` tmux — proot + tailscaled（daemon）
2. `hermes-gw` tmux — hermes gateway run
3. `cctv-map` tmux — CCTV Taiwan Map（uvicorn）
4. Dashboard — hermes dashboard --port 9229（foreground）

## 狀態檢查與故障排除

### 快速檢查清單

```bash
# 1. ttha daemon 狀態
tailscale --socket="$HOME/.tailscale/tailscaled.sock" status
# → 100.112.137.111  tailscale-termux  user@  android  ●

# 2. Serve 狀態
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve status
# → https://ttha.taile76ad.ts.net/ → proxy http://127.0.0.1:9229

# 3. SOCKS5 測試
curl -s --socks5 127.0.0.1:1080 http://100.78.85.64:9119/ | head -5
# → <!DOCTYPE html>...（Hermes 登入頁）

# 4. Serve HTTPS 測試（透過 SOCKS5）
curl -s --socks5-hostname localhost:1080 -k https://ttha.taile76ad.ts.net/ | head -5
# → HTTP/2 302 → /login?next=%2F

# 5. Dashboard 本地測試（不經 tailnet）
curl -s http://127.0.0.1:9229/ | head -5

# 6. tmux 確認
tmux ls
# → tailscale: 1 windows (running)
# → hermes-gw: 1 windows (running)
# → cctv-map: 1 windows (running)
```

### 常見問題

| 症狀 | 原因 | 解法 |
|------|------|------|
| `tailscale up` 卡住 timeout | 初次執行，尚未認證 | 檢查 `--auth-key` 是否過期，重新產生 |
| `ifconfig exec error: permission denied` | MIUI seccomp 阻擋 Go 的 `os/exec` | 用 proot 啟動（見步驟 3） |
| `tailscaled` 啟動後 `v4=false v6=false` | 同上原因 — ifconfig 失敗導致空介面列表 | 確認用 proot 啟動 |
| Serve 啟用噴錯「not enabled」 | 從未在 tailnet 管理後台授權 | 點開錯誤訊息中的啟用連結 |
| `curl https://100.112.137.111/` 噴 TLS error | Tailscale 的憑證綁 `.ts.net` 網域，不是 IP | 改用 `https://ttha.taile76ad.ts.net/` |
| `curl http://100.78.85.64:9119/` 噴 Network unreachable | Termux 無 tailnet 路由（userspace 模式） | 加 `--socks5 127.0.0.1:1080` |
| 手機瀏覽器連 `100.78.85.64:9119` 連不上 | Android App VPN 未開啟 | 打開 Tailscale App |
| `tailscale-socks-proxy.py` 報 Address already in use | Port 還在 TIME_WAIT（殺掉後 30 秒內） | 等 30 秒或換 port |
| 手機瀏覽器連 `192.168.1.105:9119` 連不上 | TCP bridge 未啟動或已停止 | 確認 `tailscale-socks-proxy.py` 在跑 |
| `tailscale serve status` 顯示 empty | serve config 被清掉了 | 重新 `serve --bg 9229` |

### 殺掉 daemon 的方法

```bash
# 乾淨關閉
tmux kill-session -t tailscale
sleep 1
rm -f ~/.tailscale/tailscaled.sock

# 暴力關閉（必要時）
pkill -9 -f "proot.*tailscaled"
pkill -9 -f "runsv.*tailscale"
```

## 架構演進（為什麼這樣設計）

### 歷史脈絡

```
階段 1 — 只有 ttha CLI
  需求: Termux 服務（Dashboard）要上 tailnet
  解法: 裝 bropines CLI，用 proot 繞過 MIUI seccomp
  問題: 手機瀏覽器無法連到其他 tailnet 節點（如 dietpi4）

階段 2 — 加上 Android App（發現衝突）
  需求: 手機瀏覽器也要連 dietpi4
  解法: 安裝 Android App，同時跑兩個
  發現: App VPN 攔截所有 100.x.x.x 流量 → ttha 收不到 incoming
  臨時解法: ttha 上跑 TCP bridge（tailscale-socks-proxy.py）

階段 3 — 混合架構（目前）
  需求: 最簡潔的日常使用體驗
  解法: 啟用 tailscale serve，ttha 負責曝光服務，App 負責 VPN
  日常: App ON → 瀏覽器直連，Termux 服務靠 serve
  備援: App OFF → TCP bridge 代理到 LAN IP

階段 4 — 可選優化（未實施）
  停掉 Android App，完全用 ttha CLI + serve
  優點: 無衝突，單一客戶端
  缺點: 手機瀏覽器需要 TCP bridge 才能連其他 tailnet 節點
```

### 為什麼不做單一客戶端方案

因為日常需求是「手機瀏覽器連 dietpi4」比「其他節點連 Termux 服務」頻率高很多。
混合架構讓最常見的操作（瀏覽器→dietpi4）零設定可用。

## 環境變數 & 憑證

| 變數 | 用途 | 位置 |
|------|------|------|
| `GITHUB_TOKEN` | GitHub 推送 | `~/.hermes/.env` |
| `NVIDIA_API_KEY` | Vision（NVIDIA 90B） | `~/.hermes/.env` |
| `OPENCODE_ZEN_API_KEY` | 主要模型（deepseek） | `~/.hermes/.env` |
| tailscale auth key | ttha 認證 | Tailscale admin console（一次性的） |

## Note

- `proot` 必須保持執行，殺掉 proot = 殺掉 tailscaled
- `down` 檔案防止 termux-services/runit 干擾自訂啟動
- MIUI 特有的 seccomp 限制；Pixel/AOSP 不需要 proot
- 初次 auth 後 state 會儲存，之後不需 `--auth-key`
- Serve 的 Let's Encrypt 憑證自動更新（Tailscale 管理）