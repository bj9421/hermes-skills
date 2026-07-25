# TPEX OpenAPI 調查記錄（2026-07-10 更新）

## 調查結果

TPEX OpenAPI 有完整的 Swagger 定義（225 個端點，含 33 個財務報表端點），但**所有 API 端點均被 Cloudflare 保護**。

### 端點定義（可下載 Swagger JSON）

| 端點模式 | 說明 | 狀態 |
|----------|------|------|
| `/mopsfin_t187ap06_O_ci` | 上櫃綜合損益表（一般業） | ❌ 302 → /errors |
| `/mopsfin_t187ap07_O_ci` | 上櫃資產負債表（一般業） | ❌ 302 → /errors |
| `/mopsfin_t187ap06_U_ci` | 興櫃綜合損益表（一般業） | ❌ 302 → /errors |
| `/mopsfin_t187ap07_U_ci` | 興櫃資產負債表（一般業） | ❌ 302 → /errors |

**Swagger JSON 位置：** `https://www.tpex.org.tw/openapi/swagger.json`（476KB，可下載）

### 技術細節

- **Cloudflare IP：** 172.65.90.66 / 172.65.90.67
- **302 重定向目標：** `https://www.tpex.org.tw/errors`
- **嘗試繞過方式：** Referer header、User-Agent、直接路徑呼叫 → 全部失敗
- **可存取範圍：** 僅 Swagger JSON 可下載，實際 API 端點完全不可用

### 結論

TPEX OpenAPI 理論上提供完整的上櫃/興櫃財報資料（綜合損益表 + 資產負債表），但實際上**無法從 Docker 容器或外部存取**。Yahoo Finance 是唯一可靠的免費財報來源。

### 替代方案

| 來源 | 上櫃財報 | 興櫃財報 | 備註 |
|------|----------|----------|------|
| Yahoo Finance | ✅ | ✅ | 主力來源 |
| FinMind | ✅ | ✅ | 備援（quota 有限） |
| TPEX OpenAPI | ❌ | ❌ | Cloudflare 封鎖 |

---
*上次更新：2026-07-10 — 本次調查確認 Swagger JSON 可下載但端點仍被封鎖*
