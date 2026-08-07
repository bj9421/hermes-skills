# 口播 script.md 品質掃描 + 批量重建（2026-08-07 實測）

背景：使用者要求「刪除所有無分段的舊文檔音檔，改用新 LLM 重作」。22 個口播資料夾中找出真正無分段者，重建成有分段有標點的版本。

## 🔴 核心技術：段落偵測必須用「空行分段」

第一次掃描用「連續行合併」當段落判定 → **誤判 20/22 個為無分段**（假陽性爆炸）。
正確做法是 `re.split(r'\n\s*\n', body)` 的**空行分段**，合併後比對 → 真正壞的只有 5 個。

判定標準（三選一即為 raw transcript 頂替 / 真無分段）：
- 標點密度 < 5 個/100 字（raw transcript 特徵，最可靠）
- 空行分段 < 3 且最長區塊 > 800 字
- script.md 與 raw.md 內容雷同（對照 frontmatter `source:` 與正文）

```python
def punct_per100(text):
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            text = parts[2]  # strip frontmatter
    body = ''.join(l.strip() for l in text.split('\n') if l.strip())
    cnt = sum(1 for c in body if c in '。，、？！；：.!,?;:')
    return round(cnt / max(len(body), 1) * 100, 1)

def real_paragraphs(text):
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            text = parts[2]
    return [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
```

**教訓**：標點密度是 raw transcript 的最強辨識訊號（<5/100 字幾乎必是逐字稿）；「單一長區塊」必須配「空行分段數」一起看，單獨用會把正常的長腳本誤判。

## 🔍 掃描流程

1. `os.walk(/opt/data/obsidian-vault/口播)` 找 `script.md`
2. 算 punct_per100 + real_paragraphs → 標記 bad
3. 對 bad 資料夾列出全部檔案（script.md / *_podcast.mp3 / *_raw.md / 逐字稿.md / .pptx / .png）
4. 確認來源：raw.md frontmatter 的 `source:` 欄位 + notehub_jobs.url（`sqlite3` 查詢要寫成 script 檔執行，inline `python3 -c` 會被 lifecycle_guard 擋）
5. **刪除前與使用者確認清單**（保留 raw.md/逐字稿.md 當重建來源）

## 🔄 批量重建（不重新下載/轉寫）

每個壞資料夾都留有 raw.md（或逐字稿.md）→ 直接餵給 `produce_podcast()`：

```python
sys.path.insert(0, '/opt/data/skills/media/youtube-note-pipeline/scripts')
from podcast import produce_podcast
transcript = open(raw_path).read()          # strip frontmatter if present
mp3 = produce_podcast(
    transcript=transcript, title=j['title'], url=j['url'],
    lang='zh', mode='solo',
    voice_a='zh-TW-HsiaoChenNeural', voice_b='zh-TW-YunJheNeural',
    out_dir=folder, video_id='',
)
```

- 單支耗時實測：100–230s（script 生成 30–60s + TTS 15–30 段）
- 背景執行 + notify_on_complete，5 支批次約 12 分鐘
- 每支完成後立刻驗證 script.md（空行分段 ≥5、標點 ≥5/100 字）+ mp3 存在
- **輸出檔名注意**：LLM 翻譯標題可能與原檔名不同（「多Agent」→「多智能體」）→ 重建後檢查資料夾內是否出現第二個 mp3，刪掉舊的缺段版

## 📊 結果樣本（驗證基準）

| 項目 | 壞（raw 頂替） | 好（LLM 生成） |
|---|---|---|
| 空行分段 | 1 | 17–36 |
| 標點/100字 | 0.3–2.9 | 6.7–10.2 |
| 內容 | 逐字稿照抄 | 自然口播開場（「哈囉，各位聽眾朋友…」）|

## ⚠️ 陷阱

- **`_parse_solo_script` 與 `_split_long_text` 都要過濾 <5 字段落**：只修一個，另一個路徑照樣觸發 edge_tts "No audio was received"（詳見 SKILL.md pitfall 52）
- 重跑「我的賈維斯」實測：新 script 30 段 vs 舊 19 段 — LLM 每次輸出不同，段落數會變動，屬正常
- 刪除前務必確認該資料夾的來源仍可重建（raw.md 在即可；`/tmp` 來源會消失 → 改用資料夾內逐字稿.md）
