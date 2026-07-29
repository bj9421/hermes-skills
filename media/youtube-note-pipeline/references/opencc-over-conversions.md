# opencc s2twp 過度轉換修正清單

`opencc` with config `s2twp` (Simplified → Traditional Taiwan with phrases) has known
over-conversion issues where it converts already-Traditional Chinese text incorrectly.
These are auto-fixed in `notehub/core/pipeline.py`'s `_convert_to_traditional()`.

## Current fixes

| Wrong (opencc output) | Correct (Taiwan) | Why it happens |
|---|---|---|
| `指令碼` | `腳本` | s2twp converts "脚本" to "指令碼", but when the source is already "腳本", opencc still converts it to "指令碼" |
| `全域性` | `全局` | s2twp converts "全局" to "全域性", a phrase more common in PRC than Taiwan |
| `演演算法` | `演算法` | Double conversion bug: 算(SC)→算法→演算法→演演算法. Single "演算法" is correct. |
| `後續連線` | `後續連接` | s2twp incorrectly maps "連接" → "連線" even when context means connection/linkage |

## Notes

- **`程序員` → `程式設計師`** (2026-07-30 observed): This is a **correct** s2twp conversion (Taiwan standard = 程式設計師, PRC = 程序員). However, it creates filename inconsistency: the directory name uses the LLM's pre-conversion title (程序員) while the MP3/filename uses the TC-converted title (程式設計師). Cosmetic only — files play fine.

## How to apply when writing conversion code

```python
import opencc
converter = opencc.OpenCC("s2twp")

# After converting, apply fixes:
FIXES = {
    "指令碼": "腳本",
    "全域性": "全局",
    "演演算法": "演算法",
    "後續連線": "後續連接",
}
text = converter.convert(text)
for wrong, right in FIXES.items():
    text = text.replace(wrong, right)
```

## Test commands

```bash
# Test a single conversion
python3 -c "
import opencc
c = opencc.OpenCC('s2twp')
print(c.convert('脚本就是全局算法的后续连接'))
# Should output: 腳本就是全域性演演算法的後續連線
# After fixes:    腳本就是全局演算法的後續連接
"
```
