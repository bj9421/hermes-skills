# Mobile App Packaging (Bookmark Manager) — TWA / Bubblewrap / iOS PWA

2026-08-02 anysearch 查證。結論：使用者手機是 **Android** → **TWA 側載（Bubblewrap）$0 是正解**；iOS PWA 能用但限制多。

## 三條路線成本對比

| 路線 | 成本 | 時間 | 適合 |
|------|------|------|------|
| 現況 PWA（加到主畫面）| $0 | 0 | 已達 90% app 體驗 |
| **TWA 側載（Bubblewrap APK）** | **$0** | 2-4 小時 | ✅ 自用推薦 |
| 上架 Google Play | 首年 ~$35-40 | 2-5 天（含 14 天測試期）| 僅要分享給大眾 |

**上架成本明細**：開發者帳號 **$25 一次性**（2026 確認無年費、無 per-app 費用；限信用卡 Visa/MC/AMEX/Discover）+ 域名 ~$10-15/年 + SSL $0（Let's Encrypt）+ 隱私政策 $0。之後每年只付域名。**隱藏成本**：新個人帳戶要 12 名測試者 × 14 天內部測試才能上生產；TWA 包裝 app 易被判「測試者參與不足」拒絕（2026 有真實案例）；需上傳身分證件驗證。

**側載缺點**：Android 首次安裝警告「未知來源」（允許一次即可）；更新要重裝 APK 無自動更新；不需要域名/assetlinks。

## 為何 TWA 而非其他方案

| 方案 | 本質 | APK 大小 | 適合 |
|------|------|---------|------|
| **TWA（Bubblewrap）** | Chrome 引擎包裝現有 PWA | ~800KB-2MB | ✅ 已有完整 PWA（manifest + sw.js + HTTPS）|
| Capacitor | WebView 包裝 | ~4MB | 無 SW 的網站 |
| Flutter | 編譯原生 ARM | ~15-25MB | 從零開發、要 iOS/原生 API |
| React Native | JS 橋接原生 | ~10-20MB | JS 團隊 |

**關鍵認知**：本專案功能全在 server 端（enrich/DoH/LLM/bot），app 只是另一個畫面 → 做 app 不影響 server 輕重。原生重寫（Flutter/RN）數週成本 + 雙 codebase 維護，單人自用完全不值得。TWA 的推播優勢已被 Telegram bot 取代（bot 回訊息本身就是推播）。

## GitHub 專案 APK 技術辨識（repo 根目錄特徵）

看到 GitHub 專案附 APK，**不要假設是 Bubblewrap**（它其實最少見，只適合已有 PWA 的專案）：

| 根目錄特徵 | 技術 |
|-----------|------|
| `pubspec.yaml` | Flutter |
| `package.json` + `android/` | React Native 或 Capacitor |
| `build.gradle` + `MainActivity.kt` | 原生 Android |
| `capacitor.config.ts` | Capacitor |
| `twa-manifest.json` | Bubblewrap / TWA（少見）|

## iOS PWA 支援（2026 查證）

**支援但體驗最差**。核心功能（瀏覽/新增/編輯）能用，限制：
- 安裝要手動：Safari → 分享 → 「加入主畫面」（無自動安裝提示，一般人不知道）
- 離線儲存 **50MB 上限**（Safari 硬限制）
- 推播 **iOS 16.4+ 才有**（2023），且需先加入主畫面
- 無背景同步；Safari 對 service worker 快取比 Chrome 積極（需 `reg.update()` 強制檢查）
- EU iOS 17.4+ 因 DMA 移除 standalone（台灣無影響）
- **TWA 是 Android 專屬，iOS 沒有等價物**；要 iOS app 只能 Capacitor/原生

## Bubblewrap 常見坑（2026 查證）

- 藍色網址列出現 = assetlinks.json 指紋錯 → 要用 **Play App Signing 的金鑰指紋**（不是 upload key；Play 會重新簽名，指紋以 Google 的為準）
- 改 assetlinks 後手機還顯示 → 清 **Chrome 資料**（不只快取）+ 重裝 app；Chrome 會快取驗證結果
- Content-Type 必須 `application/json`，不能有 redirect
- 簽名金鑰務必安全保存（證明 app 出自你）

## 建議執行順序

1. **先完成 RPi3 遷移**（server 網址會變，APK 包的 URL 跟著變）
2. 遷移後照 Obsidian 文件跑 Bubblewrap（Step 1-7，2-4 小時）
3. APK 用 Telegram 傳給自己 → 手機側載

**Obsidian 文件**：`我的筆記/開發架構/Bubblewrap-TWA-評估與操作步驟.md`（270 行完整操作步驟，獨立於遷移計劃）
