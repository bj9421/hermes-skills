# Holographic → Obsidian Sync (cron 2a7ce532d001) — Script Topology & Pitfalls

Daily 02:00 LLM-driven agent job. Pre-run script `sync_holographic_to_obsidian.sh` exports the
Holographic memory DB (`/opt/data/.hermes/memory_store.db`, table `facts`) to markdown in
`/opt/data/obsidian-vault/Holographic/`, then the agent verifies and reports fact counts.

## ⚠️ THREE divergent copies of the sync scripts — the live one is NOT the root copy

| Location | Fingerprint |
|---|---|
| `/opt/data/sync_holographic_to_obsidian.sh` + `export_holographic_to_md.py` | **NEWER** logic: writes `首頁 MOC.md` at vault root with `[[Holographic/…]]` links; NO "Using Python" echo; export prints `首頁 MOC.md: N bytes (vault root)` |
| `/opt/data/.hermes/scripts/` (same pair) | OLD logic: writes `Holographic/MOC.md` with flat `[[環境設定]]` links; no echo; PYTHON_BIN fallback `/opt/data/.hermes/.venv/bin/python3` |
| `/opt/data/scripts/` (same pair) | OLD logic identical to `.hermes/scripts`; **prints `Using Python: $PYTHON_BIN`** |

**Live-path evidence (2026-08-03 run):** pre-run output contained `Using Python: /opt/hermes/.venv/bin/python3`
(only the `/opt/data/scripts/` copy echoes this) and `MOC.md: 514 bytes` (old export writes `MOC.md`;
the newer export writes `首頁 MOC.md` at vault root). The on-disk `Holographic/MOC.md` had flat
`[[環境設定]]` links — matching the old copy.

**Lesson:** For legacy cron jobs, the script path in the cron `prompt` (e.g.
`/opt/data/sync_holographic_to_obsidian.sh`) is NOT proof of which copy ran. Fingerprint the pre-run
output (echo lines, file names, link style) before editing. Editing `/opt/data/export_holographic_to_md.py`
changes nothing about cron behavior — the live copy is `/opt/data/scripts/` unless proven otherwise.

## Dual-MOC state

- `Holographic/MOC.md` — fresh, written by the live (old) script, flat wikilinks (Obsidian resolves by filename → works).
- `首頁 MOC.md` (vault root) — STALE (only the non-live newer script writes it; last updated 2026-08-02), `[[Holographic/…]]` links.
- The cron prompt says "then update the MOC.md file" — the live script already rewrites
  `Holographic/MOC.md` automatically. The agent step is verify + fix perms, NOT hand-authoring MOC content.

## Permission pitfall (phone Sync)

`open(path, 'w')` in the export **preserves mode** on existing files (they keep 777 from an earlier
`chmod -R 777`), but a file that lost 777 — or is newly created — comes out **644**, which phone
Syncthing won't show (memory rule: 寫入 Obsidian vault 必須 chmod 777).

2026-08-03: `Holographic/MOC.md` was 644 while sibling exports were 777. Fix after any sync run:

```bash
chmod -R 777 /opt/data/obsidian-vault/Holographic/
```

## Terminal guard quirk (observed 2026-08-03)

`python3 -c "…sqlite…memory_store.db…"` and even `python3 /path/script.py` whose content queries
`/opt/data/.hermes/memory_store.db` both got blocked with *"cannot restart or stop the gateway"* —
a tirith false-positive in the same family as the documented `cat jobs.json | python3`
`pipe_to_interpreter` block (see SKILL.md Troubleshooting). Workaround: verify via existing evidence
(pre-run output fact count, file mtimes, MOC content) instead of re-querying the DB; or use a helper
script that does NOT touch `memory_store.db`. Don't retry the same blocked pattern.

## Healthy-run fingerprint

- Pre-run shows `📊 從共享 DB 讀取 N 個 facts` → per-file byte lines → `✅ 完成！N 個 facts 已匯出` → `Sync complete. 15 markdown files`.
- Fact count grows daily (500 → 515 → 539 → 559 through 2026-08-03) — dynamic, never hardcode.
