# PPT 設計模式参考

## 2026-08-07：emoji 美化系統

### 核心設計
```python
_EMOJI_KEYWORD_MAP = {
    "ai": "🤖", "artificial intelligence": "🤖",
    "data": "📊", "數據": "📊", "statistics": "📊",
    "idea": "💡", "创新": "💡", "insight": "💡",
    "rocket": "🚀", "增长": "🚀", "效率": "🚀",
    # ... 共 100+ 映射
}
```

### 使用流程
1. LLM 提取 key points（含 slide_type）
2. `_add_emoji_to_data()` 自動增強
3. dispatch 依 slide_type 選版型渲染
4. `_apply_cjk_font()` 套用字型

### 關鍵要點
- **避免重複**：檢測文本是否已有 emoji，有則跳過
- **關鍵詞匹配**：長度越長越優先（避免 "data" 匹配到 "analytics"）
- **格式統一**：`emoji + 雙空格 + 文字`
- **字型支援**：Noto Color Emoji（系統內建），Source Han Sans TC（中文主力）

### 🔴 健康醫療組（2026-08-07 新增，K2 案例）
原表 321 關鍵字全是科技/AI 主題 → 健康內容套不到 emoji（使用者嫌「太單調」）。已加：
```python
"維生素": "💊", "补充": "💊", "保健": "💊", "vitamin": "💊", "supplement": "💊",
"鈣質": "🦴", "骨骼": "🦴", "骨質": "🦴", "骨密度": "🦴", "calcium": "🦴",
"心臟": "❤️", "心血管": "❤️", "冠狀動脈": "❤️", "heart": "❤️", "cardiovascular": "❤️",
"血液": "🩸", "血壓": "🩸", "blood": "🩸",
"健康": "🌿", "養生": "🌿", "health": "🌿",
"試驗": "🔬", "研究": "🔬", "臨床": "🔬", "trial": "🔬", "study": "🔬",
"劑量": "⚖️", "dose": "⚖️", "dosage": "⚖️",
"醫生": "🩺", "醫師": "🩺", "doctor": "🩺",
```
**🔴 單字陷阱**：`_add_emoji` 是 substring 匹配 → 單字「鈣」誤配「鈣化」→ 用「鈣質」等長詞，不要單字。下關鍵字前先 `grep -oE` 報告詞頻。

### 🔴 預覽圖 emoji 渲染（ppt_preview_render.py，2026-08-07）
預覽 script 只用 Source Han Sans TC（無 emoji glyph）→ emoji 顯示 ☑ 方框。已修：
`draw_mixed()` — emoji codepoint（`\U0001F000-\U0001FAFF`/`\u2600-\u27BF`/`\u2460-\u2473`/`\uFE0F`）用 `/opt/data/fonts/NotoEmoji-Regular.ttf`（單色白線條、可辨識），其餘用主字型。驗證 emoji 真的寫入 PPTX：zipfile 抽 `<a:t>` 節點（PowerPoint 開檔才是彩色）。

## 2026-08-06：新版型系統

### 9 種版型
| 版型 | 用途 | 渲染函數 |
|---|---|---|
| hook | 開場吸睛 | `_add_hook_slide()` |
| content | 一般內容 | `_add_content_slide()` |
| data | 數字卡 | `_add_data_slide()` |
| quote | 金句 | `_add_quote_slide()` |
| qa | 問答 | `_add_qa_slide()` |
| action | 行動 | `_add_action_slide()` |
| comparison | 對比 | `_add_comparison_slide()` |
| timeline | 流程 | `_add_timeline_slide()` |
| split | 左右分頁 | `_add_split_slide()` |

### 幾何驗證腳本
```bash
python /opt/data/tmp/verify_ppt_geometry.py
```
檢查所有文字框不超出 slide 邊界（EMU 單位，tolerance 45720 ≈ 0.05 inch）。

### 常見 bug
- **split 版型錯誤映射**：曾調用 `_add_action_slide()` 而非 `_add_split_slide()`
- **內容容器太高**：content 版型 bullets 容器 4 inch → 改為 2.6 inch

## 字型優先序
1. **Source Han Sans TC**（思源黑體）- 主力
2. **Noto Sans CJK TC** - 備選
3. **Noto Sans SC** - 降權（簡體字形）
4. **Iansui** - 手寫風備選
5. **WenQuanYi Zen Hei** - 不建議（太醜）