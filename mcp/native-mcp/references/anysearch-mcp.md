# AnySearch MCP Server 設定指南

## 官方資源

| 項目 | 連結 |
|---|---|
| GitHub Repo | https://github.com/anysearch-ai/anysearch-mcp-server |
| Stars | 1.5k |
| 官網 | https://www.anysearch.com |
| API Console | https://anysearch.com/console/api-keys |

## 功能

- **General Web Search** — 自然語言查詢
- **Vertical Domain Search** — 23 垂直領域（finance, academic, code, legal, travel 等）
- **Parallel Batch Search** — 一次 1-5 題平行查詢
- **URL Content Extraction** — 抓網頁內容回傳 Markdown（上限 50,000 chars）

## 工具列表

| 工具 | 用途 |
|---|---|
| `mcp_anysearch_search` | 主要搜尋（general + 垂直領域） |
| `mcp_anysearch_batch_search` | 平行多題搜尋 |
| `mcp_anysearch_extract` | 抓取指定 URL 全文 |
| `mcp_anysearch_get_sub_domains` | 查詢垂直領域可用的 sub_domain 路由 |

## 連線方式

### Streamable HTTP（推薦）

Hermes 原生支援，無需 proxy：

```yaml
mcp_servers:
  anysearch:
    url: "https://api.anysearch.com/mcp"
    headers:
      Authorization: "Bearer ${ANYSEARCH_API_KEY}"
      X-Anysearch-Client: "mcp/1.0.0"
```

### 匿名使用

不加 Authorization header 即可匿名使用（較低限額）：

```yaml
mcp_servers:
  anysearch:
    url: "https://api.anysearch.com/mcp"
    headers:
      X-Anysearch-Client: "mcp/1.0.0"
```

## API Key 優先級

1. `--api_key` CLI flag / Authorization header
2. 環境變數 `ANYSEARCH_API_KEY`
3. `.env` 檔案
4. 匿名存取

## 垂直領域 Quick Ref

| 主題 | domain |
|---|---|
| 台股 | finance (sub_domain: finance.tw_stock) |
| 美股 | finance (sub_domain: finance.us_stock) |
| 新聞 | news |
| 健康 | health |
| 旅遊 | travel |
| 技術 | code |
| 學術 | academic |
| 法律 | legal |
| 餐廳 | business |
| 資安 | security |

## 常見問題

**Q: 沒有 API Key 能用嗎？**
A: 可以，匿名存取所有功能正常，只是限額較低。

**Q: API Key 用完了怎麼辦？**
A: 官方會自動註冊新 key 並回傳，需詢問使用者是否確認使用。

**Q: 為什麼工具沒出現？**
A: 確認 config.yaml 有 `mcp_servers.anysearch` 區塊，且 Hermes 已重啟。

## 相關技能

- `smart-search` — 搜尋紀律與工作流
- `hermes-agent` — MCP 伺服器管理命令
