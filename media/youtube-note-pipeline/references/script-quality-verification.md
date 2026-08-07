# 口播腳本品質驗證（2026-08-08 建立）

本檔紀錄 `youtube-note-pipeline` 的 script vs raw 重寫率驗證腳本與診斷 SOP。

## 快速診斷（重寫率不足時）

```bash
/opt/data/.venv/bin/python3 /opt/data/tmp/final_scan.py
```

掃全部口播資料夾，輸出：
- `sub%`：substring 覆蓋率（≥20 字連續相同，除以 script body 字數）
- `sent%`：句子層級照抄率（script 每句 ≥15 字，若 90%+ 內容嵌在 raw 中 → 照抄）
- `句數`：有效句子數
- `標點密/100`：每 100 字標點數（>15 代表異常，正常 5-10）
- 🔴 >40% 需重跑；⚠️ 30-40% 可觀察

## 判讀準則

| 指標 | 正常 | 需重跑 |
|---|---|---|
| sub%（substring） | <30% | >50% 🔴 |
| sent%（句子層級） | <20% | >40% 🔴 |
| 段落數（script） | 30-60 段 | <20 或 >100 |
| MP3 長度 | 70-110% 影片長度 | >130% 或 <50% |

## 根因分類

1. **純 Whisper 逐字稿**（raw 無標點無分段）：prompt 應該能成功改寫 → 照抄 >40% = prompt 失效
2. **口語稿/主播稿**（raw 已有人稱、串場詞）：LLM 覺得「不用改」→ 即使加強制條款也難突破（見 pitfall 68）
3. **過度濃縮**（script << raw）：prompt #14 要求「不要過度濃縮 ≥4500字」→ 矯枉過正變零濃縮（K2 pitfall 59 案例）

## 重跑方法

不需要重新下載/轉寫。直接用既有 raw.md 跑：

```python
from podcast import produce_podcast
import sys
sys.path.insert(0, "/opt/data/skills/media/youtube-note-pipeline/scripts")
# 取 raw body（不含 frontmatter 與標題）
# 見 scripts/podcast.py 的 _generate_script 呼叫處
```

更簡單：找資料夾下的 `_raw.md`，抽 frontmatter 後的 body 餵給 `produce_podcast(transcript=..., title=..., mode='solo', lang='zh', voice_a='zh-TW-HsiaoChenNeural', out_dir=...)`。

TC 轉換要手動跑：
```python
from opencc import OpenCC
cc = OpenCC('s2twp')
t = open(path).read()
t = cc.convert(t).replace('指令碼','腳本').replace('全域性','全局').replace('演演算法','演算法')
open(path, 'w').write(t)  # 不要逐字比對 zip，會全毀
```

## 2026-08-08 實測數據

| 腳本 | sub% 原始 | sent% 原始 | sub% 重跑後 | sent% 重跑後 | 改善？ |
|---|---|---|---|---|---|
| 開源全史 | 66.4% | 24.4% | 55.5% | 25.3% | ✅ |
| 死後旅程 v1 | 75.0% | 51.3% | 66.8% | 40.8% | ✅ 但有限 |
| 死後旅程 v2（強化 prompt） | 75.0% | 51.3% | 66.8% | 40.8% | 無變化（prompt 對口語稿效力有限） |
| 理解能力 | 54.0% | 18.9% | 3.4% | 3.4% | ✅ 大幅提升 |

### 死後旅程 v2 效果有限的原因

這支 raw 是**主播已經講好的口語稿**（江峰奧妙節目），非 Whisper 逐字稿：
- 已有主持人口吻（「朋友們好」「歡迎回到」）
- 句子結構完整、有敘事節奏
- LLM 認為「不用改」→ prompt 限制效果打折扣

**解法**：下次 prompt 改版時可針對此類輸入加更強制條款，或手動用 Python 做 sentence-level paraphrase（不依賴 LLM rewrite）。

## 相關 pitfall

- **pitfall 53**：script 無標點無分段 = raw transcript fallback（舊版 prompt 問題）
- **pitfall 55**：Zen 429 限流 → fallback raw（已修）
- **pitfall 59**：合成口播過度濃縮（K2 3.3x，已修）
- **pitfall 68**：重寫率不足的系統性修復
