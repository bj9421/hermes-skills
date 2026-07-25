# Web Search Backend 完整對照表

## 可用後端插件

Hermes 內建以下 web search 後端插件，位於 `/opt/hermes/plugins/web/`：

| 後端 | 免費? | 需要 API Key | 安裝需求 | 說明 |
|------|-------|-------------|---------|------|
| **Tavily** | ✅ 免費額度 | `TAVILY_API_KEY` | 無 | 推薦首選，search + extract 都支援 |
| **Brave Free** | ✅ 完全免費 | `BRAVE_SEARCH_API_KEY` | 無 | 免費 tier 1000 次/月 |
| **DuckDuckGo** | ✅ 完全免費 | 無 | `pip install ddgs` | 無需 API key，但需安裝套件 |
| **Exa** | ⚠️ 免費試用 | `EXA_API_KEY` | 無 | 需安裝 `exa-py` SDK |
| **Firecrawl** | ❌ 付費 | `FIRECRAWL_API_KEY` | 無 | 強大的網頁爬取 + 搜尋 |
| **Parallel** | ❌ 付費 | `PARALLEL_API_KEY` | 無 | 支援 search + extract |
| **SearXNG** | ✅ 自架免費 | 無 | 自建 SearXNG 伺服器 | 聚合多個搜尋引擎 |
| **xAI** | ✅ 需 Grok | `XAI_API_KEY` 或 OAuth | 無 | 透過 xAI 的 agentic web search |

## 設定方式

### 1. 設定 API Key（以 Tavily 為例）

```bash
export TAVILY_API_KEY="your-key-here"
# 或直接寫入 .env
echo 'TAVILY_API_KEY=your-key-here' >> /opt/data/.hermes/.env
```

### 2. 設定後端

```bash
hermes config set web.search_backend "tavily"
# 或同時設定 extract
hermes config set web.extract_backend "tavily"
```

### 3. 驗證

```bash
hermes config show | grep -A3 "web:"
```

## 快速選擇指南

| 需求 | 推薦後端 |
|------|---------|
| 最快上手 | **Brave Free**（免費 key，免安裝） |
| 零成本 | **DuckDuckGo**（`pip install ddgs`） |
| 最佳品質 | **Tavily**（免費額度充足） |
| 網頁內容擷取 | **Firecrawl** 或 **Tavily** |

## 已知問題

- **無後端 = 無搜尋：** `web_search` 工具存在但無後端時會靜默失敗
- **插件存在 ≠ 可用：** 目錄存在不代表已安裝/配置
- **DuckDuckGo 需手動安裝：** `pip install ddgs`
