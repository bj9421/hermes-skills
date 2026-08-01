# OpenCode Zen 免費層限流研究（2026-08-01 上網查證）

## 結論摘要

- Zen 免費模型**共用同一帳戶/IP 額度池**（約 100 req/day），**不是 per-model**
- **big-pickle 不會比 deepseek-v4-flash-free 多** — 換模型不會增加可用量
- FreeUsageLimitError 是 **IP 層級限流**（`ipRateLimiter.ts`），**有付費餘額也躲不掉**
- big-pickle 穩定性差（routing bug、too many requests loop）— 主用 deepseek-v4-flash-free 是對的

## 證據鏈（GitHub issues）

| Issue | 日期 | 發現 |
|-------|------|------|
| #15714「big pickle usage exceeded」| 2026-03 | Big Pickle 一樣撞 `Free usage exceeded`；「It is free - there's just a rate limit to how free it is」|
| #33318「Zen paid balance still hits FreeUsageLimitError」| 2026-06 | 限流是 **IP 層級**（ipRateLimiter.ts），付費餘額不 bypass；「When changing Devices it works like normal」→ 確認 IP 綁定 |
| #28166「Free Model limit」| 2026-05 | DeepSeek V4 Flash Free 掛掉時**其他免費模型同時掛** → 帳戶/共用額度 |
| #35159（7/3 故障）| 2026-07 | Big Pickle + DeepSeek + MiMo **同時**「Insufficient Balance」→ 共用後端 |
| #10404「Big Pickle too many requests loop」| 2026-01 | big-pickle 免費層 high mode 一直撞 rate limit |
| #28141「Big Pickle returns AI_APICallError」| 2026-05 | 5/18 起 routing bug（format mapping、Prima Labs invalid model）|

## 第三方評測

- ayautomate / freellm.net：Zen 免費層 ~100 requests/day（帳戶級）、7-8 個免費模型、context 8K–1M
- opencode.asia：免費層 100 requests/day（第三方資料，官方未公開數字）

## 實務含義

1. **省額度的方向**：減總請求數（合併小請求、RPM 限流、fallback 到其他 provider），不是換模型
2. **診斷 429 時**：先測其他免費模型 — 若同時掛 = 共用額度耗盡；若只有某模型掛 = 該模型問題
3. **大請求（podcast 腳本）**：Zen 免費層優先權低，45s 會 timeout（見 SKILL.md pitfall 30，已調 90s）
4. **一天內可能用完又恢復**：限流週期實測 16-24h，8/1 當日 21:14 限流 → 23:00 恢復
