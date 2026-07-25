# Railway vs Render 免費方案比較 (2026-07)

## Render 免費方案
- **費用**: $0/月，免信用卡
- **記憶體**: 512 MB / 0.1 vCPU
- **休眠**: 15 分鐘無流量 → 自動休眠（冷啟動約 1 分鐘）
- **每月 750 小時**: 每個 workspace 每月 750 小時免費實例（休眠時不計費）
- **頻寬**: 5 GB/月（Hobby 方案）
- **SQLite**: ⚠️ 每次休眠/重啟 → 本地檔案全部清空（ephemeral filesystem）
- **Cron Jobs**: ❌ 不支援
- **持久化磁碟**: ❌ Free 服務不能掛 Volume
- **資料庫**: Free Postgres 30 天過期
- **升級**: Starter $7/月（不休眠、可掛磁碟）

## Railway 免費方案
- **試用期 (Trial)**: $5 一次性（30 天），免信用卡
  - 1 GB RAM / 2 vCPU / 1 GB 暫存儲存
  - 最多 5 專案、每專案 5 服務
- **免費計畫 (Free Plan)**: $1/月（**不累積**到次月）
  - 0.5 GB RAM / 1 vCPU / 0.5 GB Volume
  - 僅 1 專案、每專案 3 服務
  - ❌ 不支援 Cron Jobs
  - ⚠️ $1 只夠跑一個極輕量 App，沒有餘裕放資料庫
- **SQLite**: 可放在 Volume 上，但 Volume 也有費用
- **資料保留**: 停擺 30 天後 Volume 資料刪除

## 結論
- **Render 免費** > Railway 免費（$1/月不夠跑 App + DB + Cron）
- 如果需要 Cron Jobs + 持久化儲存 → 需升級到付費方案
- 本機測試（RPi）是最經濟的選擇
