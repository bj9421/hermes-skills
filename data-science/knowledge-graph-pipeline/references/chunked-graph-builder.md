# Chunked Knowledge Graph Fragment Builder

**Session:** 2026-08-05, chunk 02 — 22 bookmark summaries + notehub transcripts
**Source:** `/opt/data/projects/bookmark-content-graph/graphify-out/.graphify_chunk_list_02.txt`
**Output:** `.graphify_chunk_02.json` (151 nodes, 195 edges, 3 hyperedges)

## When to use this approach

- Corpus is small (20–50 files) and already annotated/summarized
- Graphify is unavailable or the files are not code (bookmark summaries, podcast scripts, translations)
- You need cross-file semantic edges that Graphify's AST-based approach won't produce
- Output format must conform to the Hermes knowledge-graph consumer schema

## Key learnings from this session

### 1. notehub transcript files may be binary-encoded

Even though files have `.md` extension, notehub transcripts can be binary or mixed-encoding. Always read with `errors='replace'`:

```python
data = open(path, 'rb').read()
txt = data.decode('utf-8', errors='replace')
```

### 2. Cross-file edge tuple bug

The `XE()` helper resolves the file path at call time:
```python
def XE(si, se, ti, te, rel, conf, score, sf):
    X.append((nid(STEMS[si], se), nid(STEMS[ti], te), rel, conf, score, FILES[sf]))
```
The tuple already contains the resolved path as the 6th element. When iterating:
```python
for (src, tgt, rel, conf, score, sf) in X:
    ... "source_file": sf   # use sf directly, NOT FILES[sf]
```
**Bug:** using `FILES[sf]` here causes `TypeError: list indices must be integers or slices, not str` because `sf` is already a string path, not an index.

### 3. Stable node ID scheme

```python
def norm(s):
    out = []
    for ch in s.lower():
        out.append(ch if (ch.isascii() and ch.isalnum()) else '_')
    return re.sub(r'_+', '_', ''.join(out)).strip('_')

def stem_for(path):
    return norm(path[:-3] if path.endswith('.md') else path)

def nid(stem, entity):
    return f"{stem}_{entity}"
```

### 4. Validation checklist before writing output

- All node IDs match `^[a-z0-9_]+$`
- All `file_type` values in {`code`, `document`, `paper`, `image`, `rationale`, `concept`}
- All `relation` values in {`references`, `cites`, `conceptually_related_to`, `semantically_similar_to`, `rationale_for`}
- `confidence == "EXTRACTED"` → `confidence_score` must be exactly `1.0`
- `confidence == "INFERRED"` → `confidence_score` must be in {0.95, 0.85, 0.75, 0.65, 0.55, 0.9, 0.6}
- Cross-file edges reference nodes from different source files
- Max 3 hyperedges; each hyperedge must have ≥3 nodes

## Cross-file link patterns used in chunk 02

| Pattern | Example | Confidence |
|---------|---------|------------|
| Same product (script + raw transcript) | 3353-script ↔ 3353-raw | INFERRED 0.95 |
| Same product (bookmark + deep analysis) | 100-Hermes-Kanban ↔ 14-Hermes-analysis | INFERRED 0.90 |
| Similar topic (Linux on Android) | 094-home-assistant ↔ 095-linux-desktop | INFERRED 0.85 |
| Shared concept across domains | 089-Zhao-Yuanren-pinyin ↔ 104-German-pinyin | INFERRED 0.90 |
| Same product family | 78QL-Claude-Opus5 ↔ 14-Hermes-Claude-Code | INFERRED 0.75 |
| Memory/retrieval pattern | 098-MemGraph-RAG ↔ 14-Hermes-memory | INFERRED 0.65 |

## Output schema (Hermes knowledge-graph consumer)

```json
{
  "nodes": [
    {"id": "string", "label": "string", "file_type": "string",
     "source_file": "absolute_path", "source_location": null,
     "source_url": null, "captured_at": null,
     "author": null, "contributor": null}
  ],
  "edges": [
    {"source": "nid", "target": "nid", "relation": "string",
     "confidence": "EXTRACTED|INFERRED|AMBIGUOUS",
     "confidence_score": 0.0-1.0, "source_file": "absolute_path",
     "source_location": null, "weight": 1.0}
  ],
  "hyperedges": [
    {"id": "string", "label": "string", "nodes": ["nid", ...],
     "relation": "participate_in", "confidence": "INFERRED",
     "confidence_score": 0.75, "source_file": "absolute_path"}
  ],
  "input_tokens": 0,
  "output_tokens": 0
}
```