# Deployment & Migration Notes (Bookmark Manager)

2026-08-02 實測評估。結論先行：**現況（Python Flask 101MB）已是功能/資源最佳平衡，不換架構；RPi3 1GB + SSD 遷移可行。**

## 實際記憶體用量（2026-08-02 實測，ps RSS）

| 進程 | RSS | 備註 |
|------|-----|------|
| Flask + waitress server | 75 MB | 含 Flask/HTMX/DB/WAL |
| Telegram bot（stdlib-only）| 26 MB | 極輕量 |
| **基礎總和** | **~101 MB** | |
| yt-dlp 抓 metadata（暫時）| 50-80 MB | 處理完釋放 |
| edge-tts 轉 MP3（暫時）| 50-100 MB | 口播時才出現 |
| **本地 faster-whisper** | **500MB+** | 🔴 OOM 殺手，RPi3 不可用 |

RPi3 1GB 分配估算：系統 ~200MB + 專案常駐 ~120MB + 峰值 ~150MB = ~470MB，剩 ~530MB 安全。**唯一禁止項：本地 faster-whisper 永不觸發**（維持 Groq → NVIDIA API 轉寫）。

## RPi3 1GB + SSD 可行性結論

- ✅ 完全可行，推薦純 systemd（不跑 Docker）→ 省記憶體
- SSD 解決 SD 卡壽命隱憂；RPi3 USB 2.0（~35MB/s）對 DB 讀寫綽綽有餘
- ⚠️ USB SSD 供電：RPi3 USB 供電弱 → 用供電 hub / 自供電外接盒
- ⚠️ RPi3 不支援官方 USB boot → SD 開機 + SSD 存資料（/mnt/ssd）
- zram 1GB（zram-tools, zstd）防 OOM
- systemd `Restart=on-failure` + `MemoryMax` 取代 cron watchdog（避免重複機制）
- 遷移當天暫停 RPi4 的 bookmark-enrich cron，避免雙寫同一 DB

**完整遷移計劃文件**（含 systemd unit、zram、fstab、rsync 備份、驗收清單、回滾）：
`/opt/data/obsidian-vault/我的筆記/開發架構/Bookmark-Manager-遷移計劃-RPi3.md`

## 輕量替代方案比較（2026-08-02 anysearch 查證）

| 方案 | 語言 | RAM | 備註 |
|------|------|-----|------|
| bemarked | Go 單一二進位 | 5-10MB（1000+ 書籤）| 最輕 |
| Shiori | Go 單一二進位 | ~18MB | 老牌穩定 |
| neonlink | Go 單一二進位 | <50MB | SQLite FTS5 |
| Linkwarden | Node.js | ~350MB | ❌ 太重 |
| **本專案** | Python Flask | ~101MB | 客製化全功能 |

**結論：不值得換。** 本專案的客製化功能（小紅書 DoH 繞過台灣 DNS 封鎖、bilibili yt-dlp 真實標籤、Telegram bot 排隊回覆、LLM 摘要簡轉繁、notehub 口播佇列、HTMX PWA）替代品全部沒有。換 Go 方案省 ~80MB 對 1GB 機器無實際效益，卻要重寫 80% 功能。現況 = 功能全 + 101MB 輕量 + 已在 RPi3 可行性範圍內。

## 記憶體最佳化（若要再輕）

- 砍 Web UI（只留 Telegram bot）→ 省 75MB，但失去手機瀏覽/批次操作 ❌
- Flask → 極簡 http.server → 省 ~20MB，HTMX/PWA 全沒了 ❌
- 兩者皆不建議。
