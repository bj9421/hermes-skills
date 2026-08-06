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