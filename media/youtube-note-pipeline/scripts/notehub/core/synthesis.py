"""多來源合成（NotebookLM 式）— 2026-08-05 Phase 5。

把多個來源（YouTube/網頁/PDF/文字）合成一份詳細報告：
  1. 逐個 extract（重用 extractors）
  2. 各來源先個別 LLM 摘要（避免 raw text 過大）
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
NOTES_SUBDIR = "notes"

SUMMARIZE_PROMPT = """你是專業的內容摘要助手。請將以下來源內容濃縮成結構化摘要（繁體中文）。

要求：
1. 【核心重點】— 3-6 個 bullet points（**粗體**標示關鍵詞）
2. 【關鍵資訊】— 數據、日期、名稱、方法等具體資訊
3. 忠於原文，不加油添醋
4. 原文是簡體中文請轉成繁體中文（台灣用語）

內容：
"""

SYNTHESIS_PROMPT = """你是內容合成專家。以下是多個來源的摘要，請合成一份完整、詳細的整合報告（繁體中文，台灣用語）。

要求：
1. 【📌 共通主題】— 這些來源共同討論的核心主題與共識
2. 【🔍 各來源獨特觀點】— 每個來源提供的獨特資訊與角度（標明來源）
3. 【⚠️ 差異與衝突】— 各來源說法不一致、需要讀者注意的地方
4. 【💡 整體結論】— 綜合後的關鍵結論、行動建議或下一步
5. 結構化 markdown：標題用 ##，條列用 -，重要處用 **粗體**
6. 長度：至少 800 字，越詳細越好

來源摘要：
"""


def _summarize_source(text: str, title: str) -> str:
    """單一來源 LLM 摘要（過長時分塊）。"""
    chunks = _chunk_text(text, max_chars=20000, overlap=800)
    print(f"[INFO] Summarizing '{title}' ({len(chunks)} chunk{'s' if len(chunks) > 1 else ''})...",
          file=sys.stderr)
    parts = []
    for i, chunk in enumerate(chunks):
        prompt = SUMMARIZE_PROMPT + f"\n來源標題：{title}\n\n{chunk}"
        if len(chunks) > 1:
            prompt += f"\n\n（這是第 {i + 1}/{len(chunks)} 段，其他段落另外摘要。）"
        messages = [
            {"role": "system", "content": "你是專業的內容摘要助手。"},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages, max_tokens=2048, temperature=0.3)
        if result:
            parts.append(result.strip())
        else:
            print(f"[WARN] LLM 摘要失敗 chunk {i + 1}，使用原始文字", file=sys.stderr)
            parts.append(chunk[:3000])
    return "\n\n".join(parts)


def _synthesize(combined: str, lang: str = "zh") -> str | None:
    """LLM 合成最終報告（過長時分塊，最後合併）。"""
    chunks = _chunk_text(combined, max_chars=24000, overlap=1000)
    print(f"[INFO] Synthesizing {len(chunks)} chunk{'s' if len(chunks) > 1 else ''} via LLM...",
          file=sys.stderr)
    parts = []
    for i, chunk in enumerate(chunks):
        prompt = SYNTHESIS_PROMPT + chunk
        if len(chunks) > 1:
            if i == 0:
                prompt += "\n\n（這是第 1 部分，後續還有其他來源。）"
            elif i == len(chunks) - 1:
                prompt += "\n\n（這是最後一部分。請補上【整體結論】。）"
        messages = [
            {"role": "system", "content": "你是專業的內容合成專家。"},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages, max_tokens=4096, temperature=0.4)
        if result:
            parts.append(result.strip())
        else:
            print(f"[WARN] 合成失敗 chunk {i + 1}", file=sys.stderr)
    if not parts:
        return None
    return "\n\n---\n\n".join(parts)


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

    # 1. 逐個 extract + 摘要
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
            summary = _summarize_source(result.text, stitle)
            combined.append(f"### 來源：{stitle}\n來源網址：{src}\n\n{summary}")
        except Exception as e:
            print(f"[ERROR] 來源處理失敗 {src}: {e}", file=sys.stderr)
            combined.append(f"### 來源：{src}\n（此來源處理失敗：{e}）")

    if not combined:
        raise RuntimeError("所有來源都處理失敗")

    # 2. 合成報告
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
