# GraphRAG-Hybrid Extension Plan
### Multi-format ingestion + smart chunking + concept-level knowledge graph

Base repo: `rileylemm/graphrag-hybrid`

**Note for Codex (if running with the `ponytail` skill/plugin active):** this plan is compatible with ponytail's minimal-code ruleset — follow it normally. Three specific pieces are intentional and should NOT be trimmed as redundant, even though they may look like extra code for something already covered elsewhere: the `CHUNKING_STRATEGY=fixed` rollback flag (Part A2), the `via:` provenance tag on graph edges (Part D3), and running both concept-overlap linking and embedding-similarity linking as two separate mechanisms (Part D2). These exist for rollback safety and debuggability, not because the task needs them to function — keep them as specified.

---

## 0. First — answering your database question

**No, the repo does not ship with pre-built data or a pre-populated database.**

- `docker-compose.yml` only defines **empty** Neo4j and Qdrant containers — fresh instances with no data in them.
- `data/` is just an empty storage directory (for raw files / intermediate artifacts), not a database dump.
- `your_docs_here/` is where *you* drop your own markdown files.
- The database only gets populated when **you** run `scripts/import_docs.py`, which parses your docs and writes into Neo4j + Qdrant.
- Verified connection info (`neo4j/password` on ports 7474/7687, Qdrant on 6333) is just the **default local dev config** — not evidence of existing data.

So: clean slate. Good — it means the changes below can be developed and tested against a disposable database with zero risk to "real" data, since there isn't any yet.

One more relevant finding from the actual Neo4j schema (`src/utils/neo4j_utils.py`): it **already declares uniqueness constraints for `Entity.name` and `Topic.name`**, even though the current code only implements `Topic` (via `create_topic_and_relationship()`), and `Entity` is unused. This means the original author anticipated concept/entity nodes but never built the extraction pipeline for them. That's good news for us — **we're extending existing schema intent, not bolting on something foreign.**

---

## Current Codebase Map (relevant files only)

```
src/
├── config.py                    # env/config loading
├── query_engine.py              # GraphRAGQuery class — hybrid search logic
├── database/
│   ├── neo4j_manager.py         # higher-level Neo4j operations (used by import)
│   └── qdrant_manager.py        # Qdrant client wrapper
├── utils/
│   └── neo4j_utils.py           # Neo4jHelper — schema, constraints, CRUD, Cypher
└── processors/
    ├── document_processor.py    # parses MD + frontmatter, chunks, extracts relationships
    └── embedding_processor.py   # generates embeddings (all-MiniLM-L6-v2, 384-dim)
scripts/
├── import_docs.py               # CLI entry point for ingestion
└── query_demo.py                # CLI entry point for querying
```

Current chunking config (from `.env`/`config.py`): `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=200`, fixed-size with heading-path tagging.

Current Neo4j schema: `Document`, `Content` (chunk) nodes; `CONTAINS` (doc→chunk), `NEXT` (chunk→chunk), `RELATED_TO` (doc→doc), `HAS_TOPIC` (doc→topic). `Entity` node type declared but dormant.

---

## PART A — Dynamic Multi-Format Ingestion + Smart Chunking

### A1. Add a normalization layer (new file, doesn't touch existing code path)

**New file:** `src/processors/format_converter.py`

**What it does:** detects input file type and converts everything to clean Markdown *before* it ever reaches `document_processor.py`. This is the key design decision — it means `document_processor.py`'s existing frontmatter-parsing and chunking logic stays untouched and unbroken; we just widen what can feed into it.

```python
# src/processors/format_converter.py (new)

from pathlib import Path

class FormatConverter:
    def convert(self, filepath: Path) -> str:
        """Returns clean Markdown text with YAML frontmatter injected."""
        ext = filepath.suffix.lower()
        if ext == ".md":
            return filepath.read_text(encoding="utf-8")          # already correct format
        elif ext == ".pdf":
            return self._convert_pdf(filepath)
        elif ext in (".txt",):
            return self._convert_txt(filepath)
        elif ext in (".html", ".htm"):
            return self._convert_html(filepath)
        elif ext in (".docx",):
            return self._convert_docx(filepath)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
```

**Tool choice (optimized + easy, no unnecessary complexity):**

| Input type | Tool | Why |
|---|---|---|
| PDF | **Docling** (IBM, open-source) | Best table/heading preservation, runs fully local, actively maintained, pip-installable |
| Scraped HTML | `trafilatura` or `readability-lxml` → then Markdown | Strips nav/ads/boilerplate before conversion — critical for scraped pages |
| Plain `.txt` | Lightweight heuristic (paragraph-break → `##` headings if pattern detected) or pass through as one block if no structure exists | No point running a heavy parser on plain text |
| `.docx` | `MarkItDown` (Microsoft, lightweight) or `pandoc` | Fast, no GPU needed |

**Ensure it doesn't break anything:**
- Wrap each converter call in try/except; on failure, **fall back to raw text extraction** rather than crashing the whole batch import.
- Auto-generate the required frontmatter block (`title`, `category`) if the source file has none — pull `title` from filename or first heading, default `category` to `"uncategorized"` so the existing `document_processor.py` frontmatter parser never receives a malformed input.
- Add these as **optional** dependencies in `requirements.txt` (e.g., under an `[ingestion]` extras group) so the core repo still installs light if someone only wants markdown support.

### A2. Smart, structure-aware chunking (modify existing file)

**File to modify:** `src/processors/document_processor.py` → the `chunk_document()` function.

**What to change:** currently it's fixed-size (1000 chars, 200 overlap). Replace with a **hybrid strategy**:

1. First pass: split on Markdown heading boundaries (`##`, `###`) — this already partially happens via heading-path tracking, so we're extending existing logic, not replacing it.
2. Within each heading-section: if it's small enough, keep as one chunk. If too large, sub-split using the *existing* fixed-size+overlap logic as a fallback (so `CHUNK_SIZE`/`CHUNK_OVERLAP` config values stay meaningful — nothing removed, just no longer the *first* rule).
3. **Tables:** detect Markdown table blocks (regex on `|...|` patterns) and never split inside one — keep a table as an atomic chunk regardless of size, since a broken table becomes meaningless as an embedding.
4. **Code blocks:** same rule — never split inside a fenced code block.

**Config additions (`src/config.py`):**
```python
CHUNKING_STRATEGY = os.getenv("CHUNKING_STRATEGY", "structure_aware")  # "fixed" | "structure_aware"
MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", 1000))
KEEP_TABLES_ATOMIC = os.getenv("KEEP_TABLES_ATOMIC", "true").lower() == "true"
```
Default it to `"structure_aware"` but keep `"fixed"` as a fallback flag — so if the new logic ever misbehaves on a weird document, you can flip one env var back to the old, proven behavior without touching code. This is your safety net.

**Qdrant payload (`qdrant_manager.py`):** add one new field to the existing payload schema — `source_type` (`"md" | "pdf" | "html" | "docx"`) and `chunk_type` (`"text" | "table" | "code"`). This is additive only — doesn't change the vector or break existing search calls, just gives you future filtering ability.

### A3. Wire it into the import script

**File to modify:** `scripts/import_docs.py`

Currently it globs for `*.md` files. Change the file discovery to glob for the full supported set (`*.md`, `*.pdf`, `*.txt`, `*.html`, `*.docx`), and route non-`.md` files through `FormatConverter` before handing off to the existing `document_processor.process_document()` call. Everything downstream (Neo4j storage, embedding, Qdrant storage) is untouched.

---

## PART B — Concept-Level Knowledge Graph

### B1. Extend the Neo4j schema (modify `src/utils/neo4j_utils.py`)

The `Entity.name` constraint already exists in `setup_schema()` — so this step is mostly additive Cypher logic, not a schema migration risk.

**New relationship types to add:**
- `(:Content)-[:MENTIONS]->(:Entity)` — links a chunk to a concept it discusses
- `(:Entity)-[:RELATED_TO {weight: float}]->(:Entity)` — concept-to-concept relationship, weighted by co-occurrence or LLM-identified relation
- Optionally `(:Entity)-[:PART_OF]->(:Entity)` for hierarchical concepts (e.g., "Kalman Filter" is part of "State Estimation")

**New methods to add to `Neo4jHelper`:**
```python
def create_entity(self, name, entity_type=None): ...
def link_chunk_to_entity(self, chunk_id, entity_name): ...
def link_entities(self, entity_a, entity_b, rel_type="RELATED_TO", weight=1.0): ...
def get_related_entities(self, entity_name, depth=1): ...   # for multi-hop traversal
def get_documents_for_entity(self, entity_name): ...
```
These are all pure additions — no existing method signatures change, so nothing that currently calls `Neo4jHelper` can break.

### B2. Concept extraction step (new file)

**New file:** `src/processors/concept_extractor.py`

**Approach:** for each chunk, run an LLM extraction prompt asking for: key concepts/entities mentioned, and their relationships to each other. This runs against a **local Ollama model (`llama3.2:3b`)** by default — no API keys, no rate limits, no data leaving your machine. See Part C below for exact setup and speed tuning.

```python
# src/processors/concept_extractor.py (new)

import hashlib, json, sqlite3

class ConceptExtractor:
    def __init__(self, model="llama3.2:3b", host="http://localhost:11434", cache_path="concept_cache.db"):
        self.model = model
        self.host = host
        self.cache = sqlite3.connect(cache_path)
        self.cache.execute("CREATE TABLE IF NOT EXISTS cache (hash TEXT PRIMARY KEY, result TEXT)")

    def extract_batch(self, chunks: list[dict]) -> dict:
        """chunks = [{'chunk_id': ..., 'text': ...}, ...] — batch of ~8 at a time.
        Returns {chunk_id: {'entities': [...], 'relationships': [...]}}"""
        results = {}
        uncached = []
        for c in chunks:
            h = hashlib.sha256(c["text"].encode()).hexdigest()
            row = self.cache.execute("SELECT result FROM cache WHERE hash=?", (h,)).fetchone()
            if row:
                results[c["chunk_id"]] = json.loads(row[0])
            else:
                uncached.append((c, h))

        if uncached:
            prompt = self._build_batch_prompt([c for c, h in uncached])
            response = self._call_ollama(prompt)          # single call for the whole batch
            parsed = self._parse_json_safely(response)
            for (c, h) in uncached:
                r = parsed.get(c["chunk_id"], {"entities": [], "relationships": []})
                results[c["chunk_id"]] = r
                self.cache.execute("INSERT OR REPLACE INTO cache VALUES (?,?)", (h, json.dumps(r)))
        self.cache.commit()
        return results
```

**Ensure it doesn't break the pipeline:**
- Run this as a **separate, optional post-processing pass** — not inline in the critical ingestion path. If concept extraction fails or Ollama isn't running, the document still gets fully stored (chunks, embeddings, doc-level graph) exactly as before. Concept nodes are a bonus layer, never a blocker.
- **Content-hash cache is built in above** (SQLite) — re-running import on unchanged docs costs zero LLM calls.
- **Batch 6–8 chunks per Ollama call**, not one call per chunk — see Part C for why this matters on CPU-only hardware.
- Run concept extraction as a **separate script** (`scripts/extract_concepts.py`, new file) that you run *after* `import_docs.py`, rather than merging into it. Independently re-runnable and resumable — safe to stop and restart on a long batch.

### B3. Wire concepts into the Query Engine

**File to modify:** `src/query_engine.py`

Current hybrid flow: `search_qdrant()` → `expand_context()` (doc-level graph expansion) → `rank_results()`.

**Add a new step** between graph expansion and ranking: `expand_via_concepts()` — takes the entities mentioned in top-matching chunks, traverses `RELATED_TO` in Neo4j to find connected concepts, then pulls in *documents* that mention those related concepts (even if they weren't a vector-search hit). Feed these in as lower-weighted candidates in `rank_results()` so they supplement rather than override the main vector-similarity ranking.

This is additive to the ranking function — existing hybrid/category/document-retrieval search types keep working exactly as before if you don't call this new step.

---

## PART C — Local LLM Setup & Speed Tuning (Ollama on Asus VivoBook 15, no GPU)

### C1. Why local over Groq/cloud APIs for this task
Concept extraction is a bounded, structured task (not open-ended generation), so a small local 3B model is genuinely sufficient — and it removes rate-limit engineering (Groq free tier: ~30 req/min, per-model daily token caps) entirely. Groq/Gemini/OpenRouter remain useful as an **optional fallback** — e.g. via a `--backend groq` flag on `extract_concepts.py` — for a small subset of docs where you want a quality check, but the default path should be local and unlimited.

### C2. Setup
```bash
# install Ollama, then:
ollama pull llama3.2:3b
export OLLAMA_NUM_THREADS=<your CPU's physical core count>   # not logical/hyperthreaded count
```
Add `ollama` Python client (`pip install ollama`) as a dependency, defaulting `ConceptExtractor` to `http://localhost:11434`.

### C3. What actually matters for speed
- **Chunking, parsing, embeddings are not the bottleneck** — `all-MiniLM-L6-v2` runs fast on CPU regardless of LLM choice; leave this step alone.
- **The LLM step is the bottleneck.** On a non-GPU laptop, `llama3.2:3b` generates roughly **8–15 tokens/sec**.
- **Batch 6–8 chunks per call** rather than one call per chunk — cuts total call count (and fixed per-call overhead) by 6–8x. This is implemented in `extract_batch()` above.
- **Close other apps while running** — CPU inference on this class of hardware is memory-bandwidth bound; background load (especially browser tabs) measurably slows it down.
- **Run as a background/overnight job** for anything beyond ~100 documents, since the script is resumable and cache-backed.

### C4. Rough time estimates (batched, 3B model, this hardware)
| Corpus size | Approx. chunks | Est. time |
|---|---|---|
| Small (~30 docs) | ~200 chunks | ~15–20 min |
| Medium (~100 docs) | ~700 chunks | ~45–60 min |
| Large (~300 docs) | ~2,000 chunks | ~2–3 hrs |

Re-runs on unchanged docs: near-instant, thanks to the SQLite cache.

---

## PART D — Auto-Inferring Metadata & Relationships (for real-world docs with no frontmatter)

### Why this is needed
The test corpus (see `graphrag-test-corpus-spec.md`) hand-authors `category`, `related:`, and `key_concepts:` in frontmatter — that's fine for a *validation* set where you want known ground truth to check the pipeline against. But real documents you pull in later (scraped pages, random PDFs, downloaded reports) won't have any of that. If the pipeline only works when someone manually writes `related: [doc_a.md, doc_b.md]`, it isn't actually dynamic — it just moved the manual-curation problem instead of solving it. So this part makes relationship/category discovery automatic, and treats any manually-provided frontmatter as an optional override rather than a requirement.

### D1. Auto-category assignment
**File to modify:** `src/processors/format_converter.py` (the frontmatter-injection step from Part A)

When a source file has no `category`, don't default to `"uncategorized"` and stop there — instead classify it. Two options, pick based on how much you want to lean on the LLM:
- **Cheap/fast option**: embedding-similarity classification. Take the centroid embedding of chunks already stored under each existing category, embed the new document, assign it to the nearest category if similarity is above a threshold, else create a new category. Pure vector math, no LLM call, effectively free.
- **Richer option**: piggyback a category suggestion onto the *same* Ollama batch call already used for concept extraction (Part B/C) — one extra field in the JSON output (`"suggested_category": "..."`), so it costs zero additional LLM calls, just a slightly bigger prompt/response.

### D2. Auto document-relationship discovery (replaces manual `related:`)
This is really where Part B's concept graph earns its keep — it already gives you this for free, you just need to explicitly wire it in as the *primary* relationship-discovery mechanism, not just a bonus layer:

- **Concept-overlap linking**: if two documents share ≥N extracted entities (e.g., N=2), auto-create a `(:Document)-[:RELATED_TO {via: "shared_concepts", weight: shared_count}]->(:Document)` edge between them. No human ever has to write a `related:` list — it emerges from what the documents actually talk about.
- **Embedding-similarity linking** (catches cases concept extraction misses — e.g., stylistic/topical similarity without exact shared terminology): compute a document-level embedding (mean of its chunk embeddings), and auto-link documents above a cosine-similarity threshold (start around 0.75, tune from there).
- **New method on `Neo4jHelper`:** `auto_link_related_documents(doc_id, threshold=0.75, min_shared_concepts=2)` — called once per document after both its concepts and embeddings exist, runs both checks above, and writes whichever edges qualify.

### D3. How manual frontmatter fits in now
If a source `.md` file *does* have `related:`/`category` (like your test corpus, or any doc you hand-curate later), treat it as **higher-confidence, explicitly-authored** edges — tag them differently in the graph (`via: "manual"` vs `via: "shared_concepts"` vs `via: "embedding_similarity"`) so at query time you can weight manually-confirmed relationships slightly higher than inferred ones, without ever requiring manual authorship for the system to function.

### D4. Using the test corpus to validate the auto-inference
This is the other reason the hand-authored test corpus is worth keeping around even after you build D1–D3: since you already know its "true" relationships (you designed doc 9 to be the concept hub, docs 2/3/4 to share thermal/battery concepts, etc.), you can run the auto-linker over it *ignoring* its frontmatter and check whether it rediscovers the same connections. If it does, you can trust it on real, unlabeled documents. If it doesn't, you've found a tuning problem (threshold too strict/loose, concept extraction missing obvious terms) on a corpus small enough to debug in minutes.

---

## Suggested Rollout Order (safest → most ambitious)

1. **Format converter + smart chunking** (Part A) — test thoroughly on a batch of mixed PDFs/docs before touching the graph schema. This alone meaningfully improves retrieval quality.
2. **Ollama setup + entity/concept schema + extraction script** (Part C + B1 + B2) — run offline, inspect the resulting graph in Neo4j Browser before wiring it into search. Test on a small batch first to sanity-check `llama3.2:3b` extraction quality before running the full corpus overnight.
3. **Auto-inference of category + relationships** (Part D) — validate against the hand-authored test corpus (D4) before trusting it on real unlabeled documents. This is what actually makes the system dynamic rather than dependent on manual frontmatter.
4. **Query engine concept expansion** (B3) — last step, since it's the one that changes live search behavior.

At each stage, keep the old code path reachable via a config flag (`CHUNKING_STRATEGY=fixed`, or simply not running `extract_concepts.py`) so you can always roll back to the exact original repo behavior instantly.

---

## New/changed dependencies (requirements.txt)

```
docling                 # PDF -> Markdown
markitdown               # docx -> Markdown
trafilatura              # HTML boilerplate stripping
ollama                   # Python client for local llama3.2:3b concept extraction
```
External (not pip): [Ollama](https://ollama.com) installed locally, with `llama3.2:3b` pulled (`ollama pull llama3.2:3b`). Optional: a Groq/Gemini API key only if you want the `--backend groq` fallback path for spot-checking extraction quality.
