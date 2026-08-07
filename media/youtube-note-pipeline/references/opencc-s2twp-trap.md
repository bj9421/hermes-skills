# OpenCC s2twp 錯誤使用模式（2026-08-08）

## 問題復現

2026-08-08 重跑死後旅程後，手動跑 OpenCC s2twp 轉換 script.md：

```python
from opencc import OpenCC
cc = OpenCC('s2twp')
converted = cc.convert(text)
open(path, 'w').write(converted)
```

結果：**script.md 被毀** — 轉換差異 13,337 字（幾乎全毀）。

## 錯誤原因

OpenCC 的 s2twp 對**同一個字元會輸出多個可能**（非確定性）。用 `zip(script, converted)` 逐字比對時：
- 兩個字串長度不同 → 比對偏移
- 一個簡體字轉成多個繁體字 → 後續全部錯位
- 輸出結果完全錯亂

## 正確用法

```python
from opencc import OpenCC

cc = OpenCC('s2twp')
text = open(path, encoding='utf-8').read()
converted = cc.convert(text)

# ✅ 直接整個檔案替換（不要用 zip 逐字比對）
open(path, 'w', encoding='utf-8').write(converted)
os.chmod(path, 0o777)

# over-conversion fixes（同 pipeline._convert_to_traditional）
converted = converted.replace('指令碼', '腳本')
converted = converted.replace('全域性', '全局')
converted = converted.replace('演演算法', '演算法')
```

## 驗證轉換是否正確

轉換後用以下方式驗證：
```python
# 只檢查特定簡體字殘留（繁簡同形字除外）
simp_char = '晓'
if text.count(simp_char) > 0:
    print(f"殘留簡體: {simp_char} x{text.count(simp_char)}")
```

不要檢查「多少字不同」（s2twp 本來就會把一段文字轉成不同長度的文字，差字數是正常的）。

## 與 pipeline 一致性

`notehub/core/pipeline.py` 的 `_convert_to_traditional` 已經正確實現上述流程（line 142-164）。**直接呼叫 pipeline 而非手動跑 OpenCC**，避免這個坑。

## 相關

- pitfall 68：口播重跑需手動做 TC 轉換
- pitfall 55：直接 produce_podcast 重跑不含 TC，要自行手動
