# AnySearch MCP Server — 設定參考

## 官方資訊

- **GitHub:** https://github.com/anysearch-ai/anysearch-mcp-server
- **Stars:** 1.5k ⭐
- **Endpoint:** `https://api.anysearch.com/mcp`
- **Transport:** Streamable HTTP (MCP spec 2025-03-26)
- **Anonymous:** 可用（較低限額）

## Hermes config.yaml 設定

```yaml
mcp_servers:
  anysearch:
    url: "https://api.anysearch.com/mcp"
    headers:
      Authorization: "Bearer ${ANYSEARCH_API_KEY}"
      X-Anysearch-Client: "mcp/1.0.0"
```

`${ANYSEARCH_API_KEY}` 由 Hermes 在啟動時從環境變數解析。
沒設 key 就省略 `Authorization` 行，仍可匿名使用。

## 註冊後自動出現的工具

| MCP 工具名稱 | 功能 |
|---|---|
| `mcp_anysearch_search` | 一般/垂直搜尋 |
| `mcp_anysearch_batch_search` | 平行多題搜尋 |
| `mcp_anysearch_extract` | URL 全文提取 Markdown |

## 與 DDG MCP 的關係

註冊後兩者同時存在於工具清單，不再有可見性偏誤：

```
mcp_duckduckgo_search       ← DDG snippet
mcp_duckduckgo_fetch_content ← DDG 全文
mcp_anysearch_search        ← anysearch snippet（優先使用）
mcp_anysearch_batch_search  ← anysearch 平行查
mcp_anysearch_extract       ← anysearch 全文
```

優先序維持：anysearch → DDG → 其他。
