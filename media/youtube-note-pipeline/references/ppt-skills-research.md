# PPT Agent Skill 研究（2026-08-06 anysearch）

用 anysearch batch_search 找「AI agent skill powerpoint presentation generation」等 4 個 query，
22 個 GitHub repo 中篩出的重點。用途：notehub PPT 質量升級（階段 3 渲染/版型）參考。

## 工作流（找 skill repo 的有效做法）
1. `mcp__anysearch__batch_search` 一次 4 query（中英混合）
2. 結果常數百 KB → grep `github.com/owner/repo` 快速列 repo 清單
3. 用 `mcp__anysearch__extract` 深挖最相關 2-5 個 repo 的 README/SKILL.md
4. 評估維度：授權（MIT 可抄 / AGPL 只可借鑑）、技術棧（pptx vs HTML deck）、
   產出型態（.pptx / HTML / 圖）、與現有 pipeline 的整合成本

## 重點 repo

### 🥇 最相關（source-first PPTX，MIT）
**siril9/presentation-skill**（36⭐）
- outline.json（source of truth）→ python-pptx / pptxgenjs 建 .pptx — 與 notehub 同技術棧
- 16 種內容版型：split / cards-3 / timeline / stats / kpi-hero / comparison-2col / matrix / chart / table…
- 13 個風格家族（各含調色盤/字體/密度）
- 8 種構圖文法（Answer Pyramid / Evidence Plate…）+ QA 三層檢查（幾何溢出/視覺/佔位符）
- 核心哲學：「別讓簡報變成 bullet-list-after-bullet-list」— notehub ppt_gen.py 目前痛點

### 🥈 設計原則參考（HTML deck，AGPL 只可借鑑不可抄）
**op7418/guizang-ppt-skill**（23.3k⭐，歸藏，中文）
- 產出單檔 HTML 橫向翻頁 deck（非 .pptx）— 不直接適用 notehub
- 雙視覺系統：Style A 電子雜誌 / Style B 瑞士國際主義（22 種鎖定版式）
- 可借鑑原則：主題色只能從預設選（保護美學）、結構優於裝飾（不用陰影浮卡）、
  圖片第一公民（比例穩定、只裁底部）、P0-P3 分級 checklist、版式校驗器
- 內部 family 注意：Noto Sans CJK TC 家族名不是「Noto Sans TC」

### 🎨 設計風格向
- **seulee26/mckinsey-pptx** — 麥肯錫風格 PPTX
- **likaku/Mck-ppt-design-skill** — 麥肯錫 PPT 設計 skill

### 📚 綜合/官方
- **2slides/slides-generation-2slides-skills** — 2Slides 官方（ppt-prompt-resources.md 已研究過其模板）
- **kdnsna/ultimate-ppt-master-skill** — 綜合型 PPT master
- **sunbigfly/ppt-agent-skills** — 多 agent 流程

### 🎓 特定用途
- **Gabberflast/academic-pptx-skill** — 學術簡報
- **zouchenzhen/thesis-defense-pptx-skill** — 論文答辯

## 對 notehub 的建議路線（已回報使用者，未定案）
- 方案 A（推薦）：借 presentation-skill 版型多樣化精神 → ppt_gen.py 依內容類型選版型
- 方案 B：借 guizang 設計原則做檢查清單（低風險）
- 方案 C：直接換 presentation-skill 取代 ppt_gen.py（高風險整組重寫，不建議）
