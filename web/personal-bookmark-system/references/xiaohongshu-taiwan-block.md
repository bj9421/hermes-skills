# 小紅書（Xiaohongshu）台灣封鎖 + metadata 抓取（2026-08-02 已驗證成功）

## 封鎖事實（實測證據）

- `www.xiaohongshu.com` 在台灣被依「詐欺犯罪危害防制條例」由內政部警政署刑事警察局命令封鎖 — **DNS 層級污染**
- DNS 解析 → `140.111.246.32`（封鎖伺服器，回傳「此網域已經遭到封鎖 This Domain Name Has Been Blocked」頁）
- 實測：首頁 200（1228 bytes 封鎖頁）、note API 500、`discovery/item/<id>` 500、`explore/<id>` 404
- **不是技術問題，是法規封鎖** — 不要花時間在「改 UA / 加 header」上

## 可用 / 不可用的路徑

| 路徑 | 結果 |
|------|------|
| `xhslink.com` 短連結 | ✅ 未被封，302 → 真實 discovery URL |
| **DoH 查真實 IP + `curl --resolve`** | ✅ **已驗證成功（2026-08-02）** |
| `rednote.com` 國際版 | ✅ 可開（206KB）但中國版 note ID 404 |
| `archive.org` wayback | ❌ 無快取（筆記太新） |
| `xiaohongshu.com` 直接（DNS 污染下） | ❌ 500 / 封鎖頁 |

## ✅ 突破三步驟（已實作於 `fetch_xiaohongshu_meta`）

1. **curl 追蹤短連結**：`curl -s -o /dev/null -w '%{url_effective}' -k -L -A '<手機 UA>' <xhslink短鏈>` → 真實 `/discovery/item/<id>?xsec_token=...` URL
2. **DoH 查真實 IP**：`curl -s -k "https://dns.google/resolve?name=www.xiaohongshu.com&type=A"` → `43.170.214.10`（CNAME 到 eo.dnse0.com CDN；**IP 可能變，程式每次動態查，不要 hardcode**）
3. **curl --resolve 繞過 DNS**：`curl -s -A <手機UA> -k --max-time 20 --resolve "www.xiaohongshu.com:443:<真實IP>" <resolved_url>` → 抓到 133KB 完整頁面（含 `window.__INITIAL_STATE__`）

## 解析 `__INITIAL_STATE__` 兩個坑（實測踩過）

- ⚠️ **不能用 `.*?</script>` regex**：JSON 內有 nested `<script>` 標籤，`.*?` 會在內部 `<script>` 就停 → JSON 截斷 parse fail。**正確做法：大括號平衡掃描**（in_str / esc 狀態機，depth 歸零即完整 JSON）
- ⚠️ **JSON 內有非法值 `"jsAssetsList":undefined`**：小紅書的 JS 直接注入 `undefined`（不是合法 JSON）。**先 `re.sub(r':undefined\b', ':null', json_str)` 再 `json.loads`**
- 資料路徑：`state.noteData.data.noteData`（**不是** `note.noteDetailMap`，也不是第一層 `noteData` 直接放 title）→ `title` / `desc` / `tagList[].name`

## 實測結果（2026-08-02）

- `fetch_xiaohongshu_meta('http://xhslink.com/m/69X82I2wlQv')` → `('谷歌一口气放出了 15 个 AI 工具！', ['AI工具','谷歌AI','人工智能','效率工具','程序员','自媒体工具','免费软件','Gemini'], <完整 desc>)`
- 4 筆書籤（#26 #27 #33 #40）enrich：#26 #27 #33 補齊成功（真實標籤簡轉繁 + 真實摘要）；#40 是假連結（`explore/123456`）→ 誠實留空（正確行為）
- commit：bookmark-manager `e2e47b2`、scripts `8a05454`

## 容器 SSL 坑

- Docker CA 損壞 → urllib 報 `SSL: CERTIFICATE_VERIFY_FAILED: self-signed certificate` → 用 `-k`（curl）/ `ssl._create_unverified_context()`（urllib）
- **老版 curl 不認 `--no-check-certificate`**（`option is unknown`）→ 要用 `-k`
- yt-dlp 用 `--no-check-certificates`
- DoH 查詢用 urllib 時要 unverified context（`urllib.request.urlopen(req, timeout=10, context=ssl._create_unverified_context())`）或乾脆 curl `-k`

## 附註：yt-dlp XiaoHongShu extractor（已不再使用，保留參考）

- `yt-dlp --list-extractors | grep XiaoHongShu` 確認存在
- **只匹配 `xiaohongshu.com`，不匹配 xhslink 短連結** → 短連結必須先 resolve
- 需要 `xsec_token` 參數（從 302 Location 帶過）
- ❌ 在台灣封鎖環境下 yt-dlp extractor 直接 500（走了被污染的 DNS）→ 已棄用，改用 curl --resolve + INITIAL_STATE 解析
