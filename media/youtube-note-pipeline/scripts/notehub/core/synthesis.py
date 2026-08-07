"""多來源合成（NotebookLM 式）— 2026-08-05 Phase 5，2026-08-07 更新。

把多個來源（YouTube/網頁/PDF/文字）合成一份詳細報告：
  1. 逐個 extract（重用 extractors）
  2. 🔴 2026-08-07：直接使用完整逐字稿，不經過摘要濃縮（保留完整資訊）
  3. LLM 合成一份完整報告（共通主題/各來源觀點/差異/結論）
  4. 寫報告 .md 到 Obsidian notes/

兩階段設計：本模組 = 階段一（報告）。口播/PPT/圖卡 = 階段二
（由 CLI 層呼叫 podcast.py / ppt_gen.py / visual_gen.py，以報告內容為輸入）。
"""

import os
import re
import sys
from datetime import date

from ..extractors.detector import detect_source
from .llm import call_llm
from .pipeline import _chunk_text, _sanitize_filename

OBSIDIAN_BASE = "/opt/data/obsidian-vault"
NOTES_SUBDIR = "口播"  # 2026-08-07: 統一用口播資料夾，與 pipeline.py 一致

SYNTHESIS_PROMPT = """你是內容合成專家。以下是多個來源的完整內容，請合成一份完整、詳細的整合報告（繁體中文，台灣用語）。

要求：
1. 【📌 共通主題】— 這些來源共同討論的核心主題與共識
2. 【🔍 各來源獨特觀點】— 每個來源提供的獨特資訊與角度（標明來源）
3. 【⚠️ 差異與衝突】— 各來源說法不一致、需要讀者注意的地方
4. 【💡 整體結論】— 綜合後的關鍵結論、行動建議或下一步
5. 結構化 markdown：標題用 ##，條列用 -，重要處用 **粗體**
6. 長度：至少 1500 字，詳細呈現各來源的觀點和細節
7. 🔴 保留原文的重要細節、數據和觀點，不要過度濃縮

來源內容：
"""

# 🔴 2026-08-07 FIX：多 chunk 時，後續 chunk 用「接續模式」而非獨立合成。
# 原本每個 chunk 都套 SYNTHESIS_PROMPT → chunk 2 被 LLM 當成「另一批多來源」
# 重新合成 → 輸出重複的【共通主題】【來源一~七】結構，接在報告後半（K2 案例：
# 後半 4177 字是重複混亂內容）。
CONTINUATION_PROMPT = """你是內容合成專家。這是同一份多來源資料的【後續片段】（前面部分已經合成過報告）。

請將此片段的內容補充進既有報告。要求：
1. 只輸出【新增/補充的內容】，不要重新輸出整個報告、不要重複【共通主題】【整體結論】等總覽章節
2. 用「### 補充：<主題或來源>」作為小節標題，- 條列細節
3. 保留原文的重要細節、數據和觀點，不要過度濃縮
4. 繁體中文，台灣用語

後續片段：
"""


def _synthesize(combined: str, lang: str = "zh") -> str | None:
    """LLM 合成最終報告（過長時分塊，後續 chunk 走接續模式）。"""
    chunks = _chunk_text(combined, max_chars=24000, overlap=1000)
    print(f"[INFO] Synthesizing {len(chunks)} chunk{'s' if len(chunks) > 1 else ''} via LLM...",
          file=sys.stderr)
    parts = []
    for i, chunk in enumerate(chunks):
        if len(chunks) == 1:
            prompt = SYNTHESIS_PROMPT + chunk
        else:
            # 🔴 2026-08-07 FIX：chunk 0 用完整合成，chunk 1+ 用接續模式
            if i == 0:
                prompt = SYNTHESIS_PROMPT + chunk + "\n\n（這是第 1 部分，後續還有其他來源內容。）"
            else:
                prompt = CONTINUATION_PROMPT + chunk
                if i == len(chunks) - 1:
                    prompt += "\n\n（這是最後一部分。補充完成即可，不需要輸出整體結論。）"
        messages = [
            {"role": "system", "content": "你是專業的內容合成專家。"},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages, max_tokens=8192, temperature=0.4)
        if result:
            parts.append(result.strip())
        else:
            print(f"[WARN] 合成失敗 chunk {i + 1}", file=sys.stderr)
    if not parts:
        return None
    return "\n\n".join(parts)


def synthesize_sources(sources: list[str], lang: str = "zh", title_hint: str = "") -> tuple:
    """多來源合成主流程。

    Args:
        sources: 來源清單（YouTube URL / 網頁 URL / PDF / 文字檔）
        lang: 目標語言（zh）
        title_hint: 目錄命名提示（可省略）

    Returns:
        (out_dir, report_path, title)
    """
    today = date.today().strftime("%Y-%m-%d")

    # 1. 逐個 extract（保留完整逐字稿）
    combined = []
    source_titles = []
    for src in sources:
        try:
            extractor = detect_source(src)
            print(f"[INFO] Source type: {extractor.__class__.__name__} — {src}", file=sys.stderr)
            result = extractor.extract(src)
            stitle = result.metadata.get("title", src)
            source_titles.append(stitle)
            print(f"[INFO] Extracted: {stitle} ({len(result.text)} chars)", file=sys.stderr)
            # 🔴 2026-08-07：直接使用完整逐字稿，不摘要
            combined.append(f"### 來源：{stitle}\n來源網址：{src}\n\n{result.text}")
        except Exception as e:
            print(f"[ERROR] 來源處理失敗 {src}: {e}", file=sys.stderr)
            combined.append(f"### 來源：{src}\n（此來源處理失敗：{e}）")

    if not combined:
        raise RuntimeError("所有來源都處理失敗")

    # 2. 合成報告（使用完整逐字稿）
    joined = "\n\n---\n\n".join(combined)
    report = _synthesize(joined, lang)
    if not report:
        raise RuntimeError("LLM 合成失敗（所有 fallback 都空回應）")

    # 3. 寫報告到 Obsidian
    title = title_hint or (source_titles[0] if source_titles else "多來源合成")
    safe_title = _sanitize_filename(title)
    ts = today.replace("-", "")
    out_dir = os.path.join(OBSIDIAN_BASE, NOTES_SUBDIR, f"{safe_title} [synthesis-{ts}]")
    os.makedirs(out_dir, exist_ok=True)

    report_path = os.path.join(out_dir, "synthesis_report.md")
    sources_block = "\n".join(f"- {s}" for s in sources)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"---\ncreated: {today}\nsource: synthesis\ntitle: {title}\nsource_type: synthesis\ntags: [synthesis, report]\nsources:\n{sources_block}\n---\n\n# {title} — 多來源合成報告\n\n{report}")
    os.chmod(report_path, 0o777)
    print(f"[INFO] Report saved: {report_path}", file=sys.stderr)

    # 4. Index to SQLite
    try:
        from ..db.models import NoteDB
        db = NoteDB()
        db.add_note(
            title=title,
            source_type="synthesis",
            source_id=f"synthesis-{ts}",
            content=report,
            raw_content=joined,
            tags=["synthesis", "report"],
            dir_path=out_dir,
            source_url=", ".join(sources),
        )
        print("[INFO] Indexed to SQLite", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] SQLite indexing failed: {e}", file=sys.stderr)

    print(f"[INFO] Pipeline complete! Output: {out_dir}", file=sys.stderr)
    return out_dir, report_path, title
