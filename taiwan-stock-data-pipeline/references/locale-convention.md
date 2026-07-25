# 語系慣例 (Locale Convention)

## 規範

所有 `taiwan-stock-data-pipeline` 相關的 Python 腳本、Shell script 中，
**log 輸出、docstring、註解、使用者提示訊息**一律使用**正體中文（台灣）**，
禁止使用簡體中文。

## 原因

- Hermes SOUL.md 已定義「回覆時優先使用繁體中文（台灣）」
- 腳本輸出會直接顯示在 Telegram / cron log 給使用者看 → 應與 agent 回覆風格一致
- 歷史案例：`update_daily.py` 2016 年版本使用簡體中文，於 2026-07-20 全檔轉換回正體

## 如何轉換既有腳本

若發現既有 `.py` 檔包含簡體中文，使用 `opencc-python-reimplemented` 批次轉換：

```bash
# 安裝 opencc
uv pip install --python <venv_python> opencc-python-reimplemented

# 單檔轉換
python3 -c "
from opencc import OpenCC
cc = OpenCC('s2t')  # 簡 → 正
text = open('path/to/file.py', 'r').read()
converted = cc.convert(text)
open('path/to/file.py', 'w').write(converted)
print('Done')
"

# 批次掃描有簡體的檔案
grep -rn '总\|简\|脚\|汇\|软\|网\|录\|关\|伪\|优\|余\|苏\|马\|们\|头\|干\|么\|几\|只\|里\|面\|准\|发\|复\|并\|当\|后\|回\|报\|尽\|对\|从\|备\|响\|引\|历\|历\|断\|汇\|浓\|称\|胜\|审\|复\|冲\|决\|况\|余\|涂\|补\|勾\|朴\|系\|结\|运\|运\|游\|满\|减\|涡\|汉\|洁\|测\|渡\|渍\|湿\|灭\|滥\|滩\|灾\|灵\|烂\|炉\|烛\|灯\|烧\|烟\|热\|爱\|片\|版\|奖\|奖\|画\|畅\|龟\|' \
  --include='*.py' /opt/data/scripts/ | head -20

# 但注意：正體中文也有「总、汇、网」等字 — 需人工判斷，opencc 轉換更可靠
```

## 轉換記錄

| 日期 | 檔案 | 處理方式 |
|------|------|---------|
| 2026-07-20 | `/opt/data/scripts/stock-update/update_daily.py` | opencc 's2t' 全檔轉換（5,463 chars） |
