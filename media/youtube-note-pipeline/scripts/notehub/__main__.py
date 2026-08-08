"""NoteHub CLI — multi-source note pipeline.

Usage:
    python -m notehub "YouTube URL" --podcast dual --ppt --visual --lang zh
    python -m notehub "https://example.com" --organize --visual
    python -m notehub "./document.pdf" --organize --ppt
    python -m notehub "./notes.txt" --podcast solo 台女
    python -m notehub --search "keyword"
    python -m notehub --list
    python -m notehub --stats

Voice shortcuts (can be used anywhere in args):
    台男  → zh-TW-YunJheNeural      台女  → zh-TW-HsiaoChenNeural
    英男  → en-US-GuyNeural          英女  → en-US-JennyNeural
    美男  → en-US-ChristopherNeural  美女  → en-US-AriaNeural
    日男  → ja-JP-KeitaNeural        日女  → ja-JP-NanamiNeural
"""

import os
import sys

# Ensure scripts dir is in path for submodule imports
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    # Voice alias mapping
    VOICE_ALIASES = {
        "台男": "zh-TW-YunJheNeural",
        "台女": "zh-TW-HsiaoChenNeural",
        "英男": "en-US-GuyNeural",
        "英女": "en-US-JennyNeural",
        "美男": "en-US-ChristopherNeural",
        "美女": "en-US-AriaNeural",
        "日男": "ja-JP-KeitaNeural",
        "日女": "ja-JP-NanamiNeural",
    }

    def resolve_voice(v):
        """Resolve voice alias to full voice name."""
        if v and v in VOICE_ALIASES:
            return VOICE_ALIASES[v]
        return v

    # Search mode
    if "--search" in args:
        idx = args.index("--search")
        query = args[idx + 1] if idx + 1 < len(args) else ""
        if not query:
            print("Usage: python -m notehub --search \"query\"", file=sys.stderr)
            sys.exit(1)
        from notehub.db.models import NoteDB
        db = NoteDB()
        results = db.search(query)
        db.close()
        if not results:
            print("No results found.")
        for r in results:
            print(f"[{r['id']}] {r['title']} ({r['source_type']}) — {r['created_at'][:10]}")
        return

    # List mode
    if "--list" in args:
        from notehub.db.models import NoteDB
        db = NoteDB()
        notes = db.list_notes()
        db.close()
        if not notes:
            print("No notes found.")
        for n in notes:
            print(f"[{n['id']}] {n['title']} ({n['source_type']}) — {n['created_at'][:10]}")
        return

    # Stats mode
    if "--stats" in args:
        from notehub.db.models import NoteDB
        db = NoteDB()
        stats = db.get_stats()
        db.close()
        print(f"Total notes: {stats['total_notes']}")
        for stype, count in stats['by_source'].items():
            print(f"  {stype}: {count}")
        return

    # 🔴 2026-08-05 Phase 5：多來源合成模式（NotebookLM 式）
    # python -m notehub --synthesize <url1> <url2> [<url3>...] [--podcast solo|dual] [--ppt] [--visual]
    if "--synthesize" in args:
        idx = args.index("--synthesize")
        # 🔴 2026-08-05 Phase 5：過濾 flag（--lang X、--podcast X、--voice-a X、--voice-b X）
        raw = args[idx + 1:]
        sources, skip_next = [], False
        for i, a in enumerate(raw):
            if skip_next:
                skip_next = False
                continue
            if a.startswith("--"):
                skip_next = a in ('--lang', '--podcast', '--voice-a', '--voice-b', '--length')
                continue
            sources.append(a)
        if len(sources) < 2:
            print("Usage: python -m notehub --synthesize <url1> <url2> [<url3>...] "
                  "[--podcast solo|dual] [--ppt] [--visual] [--lang zh] [--voice-a 台女] [--voice-b 台男]",
                  file=sys.stderr)
            sys.exit(1)
        synth_args = args[idx + 1:]
        do_ppt = "--ppt" in synth_args
        do_visual = "--visual" in synth_args
        lang = "zh"
        if "--lang" in synth_args:
            li = synth_args.index("--lang")
            lang = synth_args[li + 1] if li + 1 < len(synth_args) else "zh"
        podcast_mode = None
        if "--podcast" in synth_args:
            pi = synth_args.index("--podcast")
            podcast_mode = synth_args[pi + 1] if pi + 1 < len(synth_args) else "dual"
        voice_a = None
        if "--voice-a" in synth_args:
            vi = synth_args.index("--voice-a")
            voice_a = resolve_voice(synth_args[vi + 1] if vi + 1 < len(synth_args) else None)
        voice_b = None
        if "--voice-b" in synth_args:
            vi = synth_args.index("--voice-b")
            voice_b = resolve_voice(synth_args[vi + 1] if vi + 1 < len(synth_args) else None)
        podcast_length = "long"
        if "--length" in synth_args:
            li = synth_args.index("--length")
            podcast_length = synth_args[li + 1] if li + 1 < len(synth_args) else "long"
            if podcast_length not in ("short", "medium", "long"):
                print(f"[WARN] Unknown --length '{podcast_length}' — fallback to 'long'", file=sys.stderr)
                podcast_length = "long"

        from notehub.core.synthesis import synthesize_sources
        out_dir, report_path, title = synthesize_sources(sources, lang=lang)

        # 階段二：依選項產出（口播 / PPT / 圖卡）
        if podcast_mode or do_ppt or do_visual:
            _scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            with open(report_path, encoding="utf-8") as f:
                report_content = f.read()
            if podcast_mode:
                from podcast import produce_podcast
                mp3 = produce_podcast(
                    transcript=report_content,
                    title=title,
                    url=", ".join(sources),
                    lang=lang,
                    mode=podcast_mode,
                    voice_a=voice_a or "zh-TW-HsiaoChenNeural",
                    voice_b=voice_b or "zh-TW-YunJheNeural",
                    out_dir=out_dir,
                    video_id="",
                    length=podcast_length,
                )
                if mp3:
                    print(f"[OK] Podcast saved: {mp3}", file=sys.stderr)
            if do_ppt:
                from ppt_gen import generate_ppt
                ppt_out = generate_ppt(report_content, title, lang=lang, out_dir=out_dir)
                print(f"[OK] PPT saved: {ppt_out}", file=sys.stderr)
            if do_visual:
                from visual_gen import generate_visual
                vis_out = generate_visual(report_content, title, lang=lang, out_dir=out_dir)
                print(f"[OK] Visual saved: {vis_out}", file=sys.stderr)
        print(f"\nOutput: {out_dir}")
        return

    # Pipeline mode (default)
    source = args[0]
    pipeline_args = args[1:]

    # Parse flags
    organize = "--organize" in pipeline_args
    podcast_mode = None
    if "--podcast" in pipeline_args:
        idx = pipeline_args.index("--podcast")
        podcast_mode = pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else "dual"
    do_ppt = "--ppt" in pipeline_args
    do_visual = "--visual" in pipeline_args
    lang = "auto"
    if "--lang" in pipeline_args:
        idx = pipeline_args.index("--lang")
        lang = pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else "auto"
    voice_a = None
    if "--voice-a" in pipeline_args:
        idx = pipeline_args.index("--voice-a")
        voice_a = resolve_voice(pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else None)
    voice_b = None
    if "--voice-b" in pipeline_args:
        idx = pipeline_args.index("--voice-b")
        voice_b = resolve_voice(pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else None)
    ppt_scheme = "dark"
    if "--ppt-scheme" in pipeline_args:
        idx = pipeline_args.index("--ppt-scheme")
        ppt_scheme = pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else "dark"
    podcast_length = "long"
    if "--length" in pipeline_args:
        idx = pipeline_args.index("--length")
        podcast_length = pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else "long"
        if podcast_length not in ("short", "medium", "long"):
            print(f"[WARN] Unknown --length '{podcast_length}' — fallback to 'long'", file=sys.stderr)
            podcast_length = "long"

    # Auto-detect voice shortcuts from remaining args (e.g. notehub file 台女)
    if not voice_a:
        for arg in pipeline_args:
            if arg in VOICE_ALIASES:
                voice_a = VOICE_ALIASES[arg]
                break

    from notehub.core.pipeline import run_pipeline
    out_dir = run_pipeline(
        source=source,
        organize=organize,
        podcast=podcast_mode,
        ppt=do_ppt,
        visual=do_visual,
        lang=lang,
        voice_a=voice_a,
        voice_b=voice_b,
        ppt_scheme=ppt_scheme,
        length=podcast_length,
    )
    print(f"\nOutput: {out_dir}")


if __name__ == "__main__":
    main()
