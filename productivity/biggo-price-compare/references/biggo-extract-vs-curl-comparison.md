# BigGo extract API vs 原始 curl 比較

## 背景

BigGo（biggo.com.tw）是 CSR 架構，商品資料由 JavaScript 動態載入。兩種抓取方式差異極大：

## 方法比較

| 特性 | curl（原始 HTML） | anysearch extract（LLM 轉換） |
|------|-------------------|-------------------------------|
| 連結數量 | ~13 個 | ~48 個 |
| 倍數差 | 基準 | 多 ~4 倍 |
| 覆蓋率 | 低（只有 SSR 骨架）| 中（LLM 嘗試還原動態內容）|
| 速度 | ~0.5s | 2-3s |
| 成本 | 免費 | 消耗 anysearch API 配額 |
| JS 執行 | ❌ 不執行 | ❌ 不執行（但 LLM 推斷）|

## curl 的問題

```bash
# 原始 HTML 抓取
curl -s "https://biggo.com.tw/s/B5/" | grep -o 'href="/r/' | wc -l
# 結果：~13 個連結
```

curl 拿到的是 SSR 骨架 HTML，大部分商品由 JavaScript 動態載入，curl 完全看不到。

## anysearch extract 的優勢

anysearch extract 使用後端 LLM 對 HTML 進行智慧解析，能：
1. 解讀 CSR 骨架中的隱含結構
2. 從有限的 HTML 中推斷更多商品連結
3. 產生更完整的 Markdown 格式輸出

```
curl:     ~13 個連結（SSR 骨架）
extract:  ~48 個連結（LLM 推斷）
瀏覽器:   更多（完整 CSR 渲染）
```

## 仍然不夠的情況

即使 extract 多抓了 4 個，**仍然無法拿到全部商品**。BigGo CSR 的完整商品列表需要瀏覽器執行 JavaScript 才能載入。

### 解決方案

多關鍵字拼湊（見 `biggo-multi-keyword-strategy.md`）：
- 單一關鍵字 extract：~12-20 筆
- 5 個關鍵字 extract + 去重：30-45 筆
- 足夠覆蓋絕大多數比價需求

## 不建議的方法

### ❌ 模擬手機 User-Agent
```bash
curl -H "User-Agent: Mozilla/5.0 (iPhone; ...)" "https://biggo.com.tw/s/B5/"
```
BigGo CSR 不依賴 UA 改變返回內容，手機版 HTML 甚至更少連結。

### ❌ anysearch extract 帶自訂 header
anysearch extract 不支援 `--header` 參數，傳入會導致拿不到任何資料。

## 結論

| 需求 | 推薦方法 |
|------|---------|
| 快速看一眼有哪些商品 | curl（免費、快速）|
| 正式比價分析 | anysearch extract（覆蓋率較高）|
| 需要全部商品 | 瀏覽器渲染（不適用於自動化）|

對於 BigGo 比價 skill 而言，**anysearch extract + 多關鍵字拼湊**是最佳平衡點：覆蓋率足夠、速度可接受、成本可控。
