# 雙 Tailscale 節點 — 完整架構參考

## 網路拓樸

```
                    Redmi Note 10 (Android 13 MIUI)
                    ==================================
                    │  WiFi IP: 192.168.1.105          │
                    │  Tailnet: taile76ad.ts.net        │
                    └──────────────────────────────────┘
                            │            │
               ┌────────────┘            └────────────┐
               ▼                                       ▼
    ┌──────────────────────┐          ┌──────────────────────┐
    │  rmn10 (Android App) │          │  ttha (Termux CLI)   │
    │  100.108.117.92      │          │  100.112.137.111     │
    │  VPN: tun0 (kernel)  │          │  Mode: userspace     │
    │                      │          │  Daemon: proot       │
    │  ┌────────────────┐   │          │                      │
    │  │ 手機瀏覽器     │   │          │  ┌────────────────┐  │
    │  │ → dietpi4:9119 │   │          │  │ Serve :443     │  │
    │  └────────────────┘   │          │  │ → :9229(Dash)  │  │
    └──────────────────────┘          │  └────────────────┘  │
                                       │                      │
                                       │  ┌────────────────┐  │
                                       │  │ SOCKS5 :1080   │  │
                                       │  │ → tailnet out  │  │
                                       │  └────────────────┘  │
                                       │                      │
                                       │  ┌────────────────┐  │
                                       │  │ TCP Bridge :9119│  │
                                       │  │ (app OFF 時)   │  │
                                       │  └────────────────┘  │
                                       └──────────────────────┘
```

## 各節點詳細資訊

### rmn10（Android App）

| 屬性 | 值 |
|------|-----|
| 節點名 | `rmn10` |
| Tailscale IP | `100.108.117.92` |
| 啟動方式 | Tailscale App → 手動開啟 VPN |
| 網路模式 | Kernel TUN (`tun0`) — 系統層級 VPN |
| 核心能力 | 手機 App 透過 VPN 路由所有 `100.x.x.x` 流量 |
| 服務 | 無（純客戶端） |
| 限制 | 無法轉發 incoming 連線給 Termux 進程 |

### ttha（Termux CLI）

| 屬性 | 值 |
|------|-----|
| 節點名 | `ttha` |
| Tailscale IP | `100.112.137.111` |
| 啟動方式 | haup.sh 自動啟動（tmux + proot） |
| 網路模式 | Userspace（無 TUN 介面）— 所有流量走 SOCKS5 |
| Daemon socket | `~/.tailscale/tailscaled.sock` |
| 核心能力 | Termux 服務的代表節點；serve 將本地 port 曝光 |
| 服務 | Hermes Dashboard（:9229 via serve）、CCTV Map（:8767） |

## 流量走向圖

### 情境 1：App ON — 手機瀏覽器連 dietpi4（每日使用）

```
手機瀏覽器輸入 http://100.78.85.64:9119/
    │
    ▼
Android VPN (tun0) 攔截 100.x.x.x 目的位址
    │
    ▼
Tailscale overlay 網路
    │
    ▼
dietpi4 收到請求 (100.78.85.64:9119 ← 100.108.117.92:xxxxx)
    │
    ▼
回應原路返回
    │
    ▼
手機瀏覽器顯示 Hermes 登入頁面 ✅
```

### 情境 2：App ON — Termux 內部連 dietpi4

```
Termux 內執行：curl http://100.78.85.64:9119/
    │
    ▼
❌ Network is unreachable
    │ (Termux userspace 沒有路由表知道 100.x.x.x 在哪)
    │
修正：curl --socks5 127.0.0.1:1080 http://100.78.85.64:9119/
    │
    ▼
ttha SOCKS5 proxy (:1080) → tailnet → dietpi4 ✅
```

### 情境 3：其他 tailnet 節點連 ttha 服務

```
外部節點輸入：https://ttha.taile76ad.ts.net/
    │
    ▼
Tailscale DNS 解析 → 100.112.137.111
    │
    ▼
手機 WiFi 收到 100.112.137.111 的封包
    │
    ├── App VPN ACTIVE: tun0 攔截 ❌ 封包給 rmn10，ttha 收不到
    │
    └── App VPN OFF: 封包到 OS → ttha userspace 收到 ✅ serve 回應
```

### 情境 4：App OFF — 手機瀏覽器連 dietpi4（備援）

```
手機瀏覽器：無法直接連 100.78.85.64（無 VPN）
    │
解法：ttha 上啟用 TCP 橋接
    │
python3 tailscale-socks-proxy.py 9119 100.78.85.64 9119
    │
    ▼
手機瀏覽器 → http://192.168.1.105:9119/
    │
    ▼
ttha :9119 收到請求
    │
    ▼
SOCKS5 127.0.0.1:1080（tailscaled 內建）
    │
    ▼
dietpi4:9119 ✅
```

## 架構決策記錄

### 為什麼同時跑兩個客戶端

| 考量 | 說明 |
|------|------|
| Termux 服務需要 tailnet 可見性 | ttha CLI 提供 Serve 功能，讓 Dashboard/CCTV 可用 HTTPS 從 tailnet 存取 |
| 手機瀏覽器需要連其他 tailnet 節點 | Android App 提供 kernel-level VPN，比 SOCKS5 proxy 簡單可靠 |
| 兩者無法合併成一個 | Tailscale 不允許單一節點同時有 kernel TUN + userspace networking |

### 為什麼不只用 Android App

Android App 的 VPN 介面 **不提供 incoming 連線轉發給 Termux 進程**。其他 tailnet 節點連不到 `100.108.117.92:9229`。

### 為什麼不只用 ttha CLI

ttha 的 SOCKS5 proxy 可以讓手機瀏覽器經由 ttha 連到 dietpi4，但需要額外設定（瀏覽器代理或 TCP bridge）。日常操作比開關 App VPN 麻煩。

### 為什麼用 proot 而不是 su/root

Termux 無 root 權限。proot 在 userspace 用 ptrace 攔截 syscall，不需要 root。MIUI 13 不允許未 root 裝置的 `clone3` syscall。

### 為什麼 tailscale serve 走 HTTPS 443 而不是其他 port

Tailscale serve 預設用 443 以取得標準 HTTPS 憑證（Let's Encrypt）。瀏覽器對 443 以外的 HTTPS port 支援較差（URL 必須寫 `https://domain:port`）。

## 復原程序

### 完整砍掉重設

```bash
# 1. 清除 ttha 狀態
tmux kill-session -t tailscale 2>/dev/null || true
pkill -9 -f "proot.*tailscaled" 2>/dev/null || true
rm -rf ~/.tailscale/

# 2. 清除 serve config
tailscale --socket="$HOME/.tailscale/tailscaled.sock" serve --https=443 off 2>/dev/null || true

# 3. 清除 Android App 資料
# 設定 → 應用程式 → Tailscale → 清除資料

# 4. 重新安裝
curl -fsSL https://raw.githubusercontent.com/bropines/tailscale-termux-cli/main/remote-install.sh | bash
```

### 緊急恢復（haup.sh 出問題時）

```bash
# 手動啟動 tailscaled
touch $PREFIX/var/service/tailscaled/down
pkill -9 -f "runsv.*tailscale" 2>/dev/null || true
rm -f ~/.tailscale/tailscaled.sock
proot -b /proc -b /sys tailscaled \
    --statedir="$HOME/.tailscale" \
    --socket="$HOME/.tailscale/tailscaled.sock" \
    --tun=userspace-networking \
    --socks5-server=localhost:1080 &

# 檢查
sleep 2
tailscale --socket="$HOME/.tailscale/tailscaled.sock" status
```

## 變更歷史

| 日期 | 變更 | 理由 |
|------|------|------|
| 2026-07-26 | 初始安裝 bropines CLI + proot | 需要 ttha 節點正常運作 |
| 2026-07-27 | 發現雙節點衝突 | 同時開 App 時 ttha incoming 被擋 |
| 2026-07-27 | 加入 TCP bridge（tailscale-socks-proxy.py） | App OFF 時手機仍可連 dietpi4 |
| 2026-07-28 | 啟用 tailscale serve（:443→:9229） | 取代直接 tailnet IP 連線，統一用 HTTPS |
| 2026-07-28 | 驗證混合架構可行 | App ON 時瀏覽器直連 + serve 正常 ✅ |
| 2026-07-28 | 視覺模型改用 NVIDIA 90B（config 更新） | Gemini free tier 20/天不夠用 |