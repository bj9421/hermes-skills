# LLM Rate-Limit Landscape（2026-08-01 調查）

所有會打 LLM API（Zen/AGNES/Groq）的 cron + 腳本完整地圖，與跨 process 限流缺口。

## 完整地圖

| 觸發者 | 頻率 | 打哪個 LLM | 有無限流 |
|---|---|---|---|
| notehub worker（llm.py `call_llm`） | 每次佇列處理（密集） | Zen→AGNES→Groq | ✅ threading.Lock |
| bookmark-enrich（cron deb71e8d5dbd，每 10 分鐘） | 最多 5 筆/輪 | Zen→AGNES→Groq（llm_enhance.py） | ❌ 無 |
| bookmark-bot.py（Telegram @add2bm_bot 即時） | 每次訊息 | Zen（`llm_call`，無 fallback） | ❌ 無 |
| run_tagging.py（bookmark-manager） | 手動/批次 | call_llm | ❌ 無 |
| opencode_http_worker.py | 背景任務 | OpenAI-compatible API | ❌ 無 |
| agnes_image.sh | 手動 | AGNES 圖片（images/generations） | ❌ 無 |
| Auto Memory Scanner / daily-review / 每日對話日誌 | 定時 | Hermes 主模型 | 內建 429 處理 |

## 現有限流值（notehub/core/llm.py）

| Provider | 間隔 | RPM | 實作 |
|---|---|---|---|
| Zen | 3.0s | 20 | `_rate_limit()` + `_zen_last_call` |
| AGNES | 2.0s | 30 | `_rate_limit()` + `_agnes_last_call` |
| Groq | 2.0s | 30 | 共用 `_nvidia_last_call`（名稱沿用，勿誤以為是 NVIDIA） |

## 核心缺口：threading.Lock 只擋單 process

`_rate_limit()` 用 module 變數 + `threading.Lock` → **同 process 內有效**。bookmark-enrich（cron 每次新 process）和 bookmark-bot（常駐 process）各自計時，互相不知道 → 同一秒可能多個請求同時打到 Zen。

## 風險評估

- Zen 免費 20 RPM；bookmark-enrich 10 分鐘才 ≤5 次 → 單獨跑不會撞
- 真正的風險是**多 process 併發**：enrich + bot 同時、或多個密集 worker 並行
- 過去 Zen 被打到 429 retry-after 39372s（~11 小時）就是沒限流的後果

## 全局化解法（proposal，尚未實作）

檔案鎖 + 時間戳記檔（跨 process 全域排隊）：

```python
# /opt/data/scripts/llm_rate_limit.py（proposal）
import time, fcntl, json
STATE_FILE = '/opt/data/scripts/.llm_rate_state.json'
INTERVALS = {'zen': 3.0, 'agnes': 2.0, 'groq': 2.0}

def wait(provider):
    with open(STATE_FILE, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        state = json.load(f) if f.tell() else {}
        last = state.get(provider, 0)
        wt = INTERVALS[provider] - (time.time() - last)
        if wt > 0:
            time.sleep(wt)
        state[provider] = time.time()
        f.seek(0); f.truncate(); json.dump(state, f)
        fcntl.flock(f, fcntl.LOCK_UN)
```

套用對象：llm.py、llm_enhance.py、bookmark-bot.py、run_tagging.py、opencode_http_worker.py。

**替代方案 B**：錯開 cron 時間（enrich 10min→15min、每輪 5→3 筆），零程式碼但治標。

## 決策狀態

調查完成（2026-08-01），使用者尚未決定走 A（檔案鎖）或 B（錯開時間）。下次 session 若使用者問起，直接引用此結論。
