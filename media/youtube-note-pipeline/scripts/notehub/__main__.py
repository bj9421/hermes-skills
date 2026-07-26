"""NoteHub CLI — multi-source note pipeline.

Usage:
    python -m notehub "YouTube URL" --podcast dual --ppt --visual --lang zh
    python -m notehub "https://example.com" --organize --visual
    python -m notehub "./document.pdf" --organize --ppt
    python -m notehub "./notes.txt" --podcast solo
    python -m notehub --search "keyword"
    python -m notehub --list
    python -m notehub --stats
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
        voice_a = pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else None
    voice_b = None
    if "--voice-b" in pipeline_args:
        idx = pipeline_args.index("--voice-b")
        voice_b = pipeline_args[idx + 1] if idx + 1 < len(pipeline_args) else None

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
    )
    print(f"\nOutput: {out_dir}")


if __name__ == "__main__":
    main()
