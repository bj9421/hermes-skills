# Bookmark Bot (@add2bm_bot) 技術細節

## 程式位置
- Bot script: `/opt/data/scripts/bookmark-bot.py` / `/opt/data/.hermes/scripts/bookmark-bot.py`
- Token: `/opt/data/.bookmark-bot-token`
- Watchdog: `/opt/data/.hermes/scripts/bookmark-bot-watchdog.py` (no_agent cron, every 5min)

## LLM 即時處理（HTTP.client vs urllib）

Bot 使用 `http.client.HTTPSConnection` 而非 `urllib.request` 來呼叫 OpenCode Zen API：

```python
conn = http.client.HTTPSConnection('opencode.ai', timeout=25)
body = json.dumps({'model':'deepseek-v4-flash-free', 'messages':[...]}, ensure_ascii=False)
conn.request('POST', '/zen/v1/chat/completions', body.encode(), {'Content-Type':'application/json'})
resp = conn.getresponse()
data = json.loads(resp.read().decode())
conn.close()
```

⚠️ `urllib.request.urlopen` 對 `https://opencode.ai/zen/v1/chat/completions` 回 403，但 `http.client` 和 `curl` 都正常。原因不明。本機 API（localhost:5001）和 Telegram API 不受影響，仍用 urllib。

## 回覆格式

```
✅ **已收藏** (id#5)
📌 網頁標題
📝 摘要前 200 字
🏷️ tag1,tag2,tag3
```

## 啟動/停止

```bash
# 啟動（背景）
python3 /opt/data/.hermes/scripts/bookmark-bot.py "$(cat /opt/data/.bookmark-bot-token)" &

# 停止（清所有殘留）
pkill -f bookmark-bot.py

# 檢查
pgrep -f bookmark-bot.py
```

## 除錯

- Log 等級：`logging.INFO`，輸出到 stdout
- 查看：`process(action='log', session_id='...')` 或 `journalctl`（如果用 systemd）
- 常見問題：
  - `Process err: 0` → 可能是 exception 沒被正確 catch（檢查 `import urllib.error`）
  - `Conflict: terminated by other getUpdates request` → 同 token 兩個 bot 衝突，`pkill -f bookmark-bot.py` 清乾淨
  - `TG API error: {'ok': False, ...}` → Telegram API 參數錯誤（如 `allowed_updates` 拼錯）

## 已知限制

- 一次只處理第一條 URL（`urls[:1]`），避免多連結時的回覆混亂
- LLM timeout 設 25s，超過會存 `(summary='', tags='')`，由 cron 後補
- 使用 `Markdown` parse_mode 回覆，Tag 可能跟 Telegram 的 `_`/`*` 衝突
