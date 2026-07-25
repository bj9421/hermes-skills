---
name: smart-search
description: "搜尋策略 — anysearch 主力 + DDG 備援 + 最低 token 消耗原則，適用寫文、查 bug、除錯、技術研究"
version: 1.2.0
author: Hermes Agent
platforms: [linux]
---

# 智慧搜尋技能 (Smart Search)

## 觸發條件

- 需要搜尋資訊（寫文查證、查 bug、找技術方案、故障排除）
- 使用者說「查一下」「搜尋」「確認」「研究一下」
- 錯誤訊息需要找解決方案

## ⚠️ 賽前檢查（強制，不可跳過）

每次觸發搜尋前，**強制優先使用 anysearch MCP 工具**：

| 工具 | 用途 |
|---|---|
| `mcp_anysearch_search` | 主要搜尋（general web + 23 垂直領域） |
| `mcp_anysearch_batch_search` | 一次查 1-5 題（平行） |
| `mcp_anysearch_extract` | 抓指定 URL 的全文（Markdown） |

| MCP 工具狀態 | 行動 |
|---|---|
| ✅ 出現在工具清單 | **強制優先使用 anysearch MCP** |
| ❌ 未出現（MCP 未連線） | 降級到 `mcp_duckduckgo_search`，並回報問題 |

> 🔴 **紀律提醒：** 任何search MCP 已註冊為 `mcp_servers.anysearch`（Streamable HTTP）。搜尋時 `mcp_anysearch_search` 跟 `mcp_duckduckgo_search` 同級可見，**不可跳過 anysearch 直接走 DDG**。這是這份技能**最常被違反的規則**，使用者會直接點出來。強制遵守優先序。

## 🧠 根本原因：MCP 可見性偏誤（MCP Visibility Bias）

每次搜尋跳過 anysearch 不是「忘了」，而是**系統性的工具可見性問題**：

| 工具 | 載入方式 | 在你眼中 | 使用成本 |
|---|---|---|---|
| `mcp_duckduckgo_search` | 自動載入 MCP | ✅ 直接可見，點擊即用 | 0 思考成本 |
| `mcp_duckduckgo_fetch_content` | 自動載入 MCP | ✅ 直接可見 | 0 思考成本 |
| `anysearch search` | `terminal()` 繞 CLI | ❌ 不可見，需主動想起 | 需記憶 + 手動組合 |

**結論：這不是意志力問題，是 UI/UX 問題。** 當一個工具是內建的一級工具，另一個需要自己記得敲 CLI，大腦永遠走阻力最小的路。解決方案只有一條路：**把 anysearch 也註冊成 MCP 伺服器**，讓它跟 DDG 站在同一個起跑線。

## 🔧 結構性解法：註冊 anysearch MCP Server（治本）

將 anysearch 加入 `mcp_servers`，使其工具自動出現在工具清單中：

```yaml
mcp_servers:
  anysearch:
    url: "https://api.anysearch.com/mcp"
    headers:
      Authorization: "Bearer ${ANYSEARCH_API_KEY}"
      X-Anysearch-Client: "mcp/1.0.0"
```

註冊後的工具清單變成：

| 工具 | 來源 |
|---|---|
| `mcp_duckduckgo_search` | DDG MCP |
| `mcp_duckduckgo_fetch_content` | DDG MCP |
| `mcp_anysearch_search` | anysearch MCP |
| `mcp_anysearch_batch_search` | anysearch MCP |
| `mcp_anysearch_extract` | anysearch MCP |

**兩邊都是 MCP 工具，沒有誰隱形。** 之後搜尋時可以同時看到 `mcp_duckduckgo_search` 和 `mcp_anysearch_search`，不再有「看不到所以沒用」的藉口。

> anysearch MCP Server 支援 Streamable HTTP，不需要本地 proxy 或 install。Hermes 可透過 `url` 直接連線。沒 API Key 也能匿名使用（較低限額）。詳細參考：https://github.com/anysearch-ai/anysearch-mcp-server

## 核心邏輯

搜尋管道優先序，由高到低：

```
① anysearch（主力）— MCP 工具，有 API Key，廣度深度最佳
   ├─ mcp_anysearch_search（垂直領域 → snippet 摘要）
   ├─ mcp_anysearch_extract（等同 Jina Reader，抓全文 Markdown）
   └─ mcp_anysearch_batch_search（一次多題，平行查）

② DDG search（備援）— MCP 工具，免 Key 零成本
   ├─ mcp_duckduckgo_search（snippet 摘要）
   └─ mcp_duckduckgo_fetch_content（全文純文字，僅 snippets 不足時用）

③ Jina Reader / Crawl4AI — 除非 extract 不夠乾淨，否則跳過
```

## 省 Token 原則

| 原則 | 說明 |
|---|---|
| **snippet 優先** | ~30 token → 夠用就不要抓全文，80% 問題 snippet 解決 |
| **extract 次之** | 需要全文時用 anysearch extract（乾淨 Markdown） |
| **fetch_content 最後** | DDG 純文字版，token 最重，僅備援用 |
| **delegate 分流** | 大量搜尋（5+ 題）→ 子代理走 Groq 做搜尋+摘要 → 主模型只做事 |
| **80/20 法則** | snippet 解決 80%，只對 20% 有爭議的點展開全文 |

## 各工具 Token 消耗估算

| 動作 | Token | 適用場景 |
|---|---|---|
| DDG search | ~200 | 快速 snippet，錯誤訊息秒查 |
| anysearch search | ~300 | snippet + 垂直領域更精準 |
| anysearch extract | ~1,200 | 乾淨 Markdown 全文 |
| DDG fetch_content | ~4,500 | 純文字備援，含雜訊 |
| Jina Reader | ~1,200 | 等同 extract，備用 |
| Crawl4AI | ~600 | 最乾淨但 RPi4 資源重 |

**典型單次任務：** search × 3 + extract × 1 = ~2,100 token

## 垂直領域快速參考

anysearch 指定 domain 後搜尋準確度比一般搜尋高 3 倍：

| 主題 | domain | 備註 |
|---|---|---|
| 台股/股價 | finance | sub_domain: finance.tw_stock |
| 美股/財報 | finance | sub_domain: finance.us_stock |
| 新聞/時事 | news | — |
| 健康/醫療 | health | — |
| 旅遊/景點 | travel | — |
| 技術/程式 | code | — |
| 學術/論文 | academic | — |
| 法律/判決 | legal | — |
| 餐廳/營業時間 | business | — |

## 三種情境工作流

### 📝 寫文章查證

```
mcp_anysearch_search "主題 關鍵資訊"
  └─ snippet 夠 → 直接寫入
  └─ 有疑點 → mcp_anysearch_extract "<url>"（抓全文確認）
```

### 🐛 查 bug / 故障排除

```
mcp_anysearch_search "<錯誤訊息>"
  └─ snippet 有解法 → 直接套用
  └─ 需要更多 → mcp_anysearch_extract "<stackoverflow連結>"
  └─ 找不到 → mcp_duckduckgo_search 不同引擎再試
```

### 🔬 技術研究

```
主題較明確 → mcp_anysearch_search（垂直領域，精準命中）
主題較模糊 → 先用 mcp_duckduckgo_search 打水漂（免成本）
          → 再 mcp_anysearch_search 垂直深入
大量資料整理 → delegate_task 分流到免費模型做摘要
```

## 大量查核 / 搜尋（5+ 題）

用 delegate 分流，避免主力模型被搜尋消耗：

```
delegate_task(
  goal="搜尋以下 5 件事，用 mcp_anysearch_search/mcp_duckduckgo_search 查，整理成摘要",
  context="""題目：
1. ...
2. ...

原則：mcp_anysearch_search snippet 夠就用，不足才 mcp_anysearch_extract。
      每題最多看 2 個來源就收斂。
      用中文回覆摘要。"""
)
```

之後主模型拿到摘要直接做事，token 省 60%。

## 變更日誌

| 日期 | 變更 |
|---|---|
| 2026-07-17 | 遷移 from CLI to MCP: 將 anysearch 註冊為 `mcp_servers.anysearch`（Streamable HTTP），工具名從 `anysearch search`/`extract`/`batch_search` 改為 `mcp_anysearch_search`/`extract`/`batch_search`。所有情境工作流、範例、陷阱說明同步更新。 |

## 極簡模式

使用者說「直接用現有資料」、「不用查了」→ **跳過所有搜尋**，只靠既有知識。除非使用者明確要求查證才啟動搜尋。

## 輸出格式原則

搜尋結果整理成回答時：

1. **連結內嵌在初始回應** — 特別是工具/資源排名，每個項目附上完整 URL。使用者會直接要求補上，不要等第二輪才給。
2. **表格優先** — GitHub Stars、安裝量、排名等結構化資料用 Markdown 表格呈現，比段落更容易掃讀。
3. **多層次閱讀** — 結論 + 數字摘要放最前面，再展開詳細表格，最後才放安全提醒或脈絡補充。使用者是務實決策型，需要快速抓到重點。
4. **連結要明確** — 給完整網址（GitHub repo、skills.sh 頁面等），不要只說「搜尋某倉庫」或省略協定。

## 已知陷阱

1. **過度搜尋** — snippet 就夠的不要硬抓全文。使用者說「夠了」「不要搜尋了」時立即停止。
2. **anysearch extract 可取代 Jina** — 兩者品質相近，不需多繞路。
3. **DDG fetch_content 是最重的選項** — 只有在任何工具都不可用時才用它。
4. **delegate 分流記得設語言** — 中文任務 context 要寫「用中文回覆摘要」。
5. **RPi4 不適合 Crawl4AI** — 除非明確批次爬取需求（5+ 頁），否則不裝。
6. **先 snippet 後 extract** — 順序錯誤會浪費 token。先確保 snippet 不夠才拉全文。
7. **跳過 anysearch 直接走 DDG** ⚠️ 最常見也最嚴重的違規。根本原因是 MCP 可見性偏誤（參見🧠根本原因章節）。現在 anysearch 已註冊為 `mcp_servers.anysearch`，搜尋時 `mcp_anysearch_search` 跟 `mcp_duckduckgo_search` 同時出現在工具清單中，**再也沒有「看不到所以沒用」的藉口**。強制遵守優先序。
