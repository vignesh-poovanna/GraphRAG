# decisions.md — GraphRAG-Hybrid Extension

## Part A — Format Converter + Smart Chunking

### D-01 · FormatConverter is a pre-pass, not inside document_processor
**Decision:** new `format_converter.py` normalises all formats to Markdown *before* `document_processor.py` sees it.
**Why:** `document_processor.py` already works. The cleanest extension point is a normalization layer that produces the exact string format it already expects, so it stays untouched.
**Tradeoff:** two function calls (convert + process) instead of one, but the caller is trivial and the separation keeps both modules independently testable.

---

### D-02 · Optional deps lazy-imported, not hard requirements
**Decision:** `docling`, `markitdown`, `trafilatura` are imported inside their converter methods, listed as comments in `requirements.txt`.
**Why:** someone only using `.md` files should not pull in docling (a large ML package). Missing lib failures surface only for that file type, not at startup.
**Tradeoff:** runtime rather than install-time errors for missing libs. Mitigated by the fallback chain + warning log.

---

### D-03 · Fallback chain on converter failure — raw text, not crash
**Decision:** every `_convert_*` method falls back to plain text read on ImportError or any exception, then injects frontmatter and continues.
**Why:** a batch of 200 files should not die because one PDF has a corrupted header.
**Tradeoff:** silently-degraded quality for that one file, but always visible in logs at WARNING level.

---

### D-04 · Structure-aware chunker splits on `##`/`###`, not `#`
**Decision:** heading split only fires on level-2+ headings.
**Why:** H1 is almost always the document title. Splitting there creates a zero-content first chunk. H2/H3 are meaningful section breaks.

---

### D-05 · Atomic block protection via placeholder substitution
**Decision:** tables and code fences are replaced with `\x00ATOMIC_N\x00` sentinels before heading-split, then restored after.
**Why:** regex-split on headings would otherwise carve through a table mid-row. A broken table fragment is meaningless as an embedding.
**Tradeoff:** `\x00` is a null byte — reliable sentinel, invalid in normal markdown text. Vanishingly unlikely to collide with real content.

---

### D-06 · CHUNKING_STRATEGY=fixed is a one-var rollback
**Decision:** `config.py` defaults to `structure_aware`; `fixed` calls the original `_fixed_chunks()` method unchanged.
**Why:** explicit requirement in the implementation plan for rollback safety.

---

### D-07 · chunk_type and source_type in Qdrant payload only — no new index
**Decision:** additive payload fields, no new Qdrant index.
**Why:** they are metadata for future filtering, not a field searched today. Premature indexing slows upserts for zero current benefit.

---

### D-08 · import_docs.py walks files itself instead of delegating to process_directory()
**Decision:** `import_docs.py` does its own `os.walk` + per-file conversion loop.
**Why:** `process_directory()` had no way to accept a converter instance. Walking in `import_docs.py` lets the converter be a proper dependency without changing `process_directory()`s signature. `process_directory()` still works independently.

---

### D-09 · Tool choices for format conversion

| Format | Tool | Reasoning |
|--------|------|-----------|
| PDF | docling (IBM) | Best table/heading fidelity of pip-installable PDF libs; fully local; actively maintained. pypdf/pdfminer lose table structure. |
| DOCX | markitdown (Microsoft) | Lightweight, no GPU, pip install. pandoc requires a system binary. |
| HTML | trafilatura | Built for boilerplate stripping (nav/ads/footer); more maintained than readability-lxml. |
| TXT | none | Pass-through is correct; the chunker handles unstructured paragraphs. |

---

## Part C + B — Ollama Setup + Concept Extraction

### D-10 · Concept extraction as a post-processing pass, not inline
**Decision:** `extract_concepts.py` is a separate script run after `import_docs.py`, not merged into it.
**Why:** concept extraction is slow (CPU-bound LLM). If it ran inline, one Ollama failure would kill an entire import. Running separately: docs are always stored fully first, extraction is independently restartable, and the cache makes re-runs free on unchanged chunks.
**Tradeoff:** two commands to run instead of one. Acceptable — the plan explicitly specifies this separation.

### D-11 · SQLite for the concept cache, not Redis/file-per-chunk
**Decision:** a single SQLite file keyed by SHA-256 of chunk text.
**Why:** zero new infrastructure. SQLite is stdlib. SHA-256 of chunk text is the correct cache key — if the text changes, the cached extraction is stale, and the key naturally changes. A file-per-chunk approach would create thousands of small files.
**Tradeoff:** SQLite has a single-writer limit, but this script runs single-threaded by design (CPU-bound Ollama is the bottleneck, not Neo4j).

### D-12 · Batching 6-8 chunks per Ollama call
**Decision:** DEFAULT_BATCH_SIZE=7. Build a single prompt containing N chunk texts, get a single JSON response keyed by chunk_id.
**Why:** per-call overhead on local Ollama (~1-2s model load amortized + HTTP round-trip) dominates on a 3B model. 7x fewer calls = ~7x faster for the same total tokens. The plan specifies this explicitly.
**Tradeoff:** larger prompts risk the model losing track of later chunks. 7 chunks * 800 chars cap = ~5600 chars input — well within llama3.2:3b's 8k context window.

### D-13 · Temperature=0 for concept extraction
**Decision:** `options={"temperature": 0.0}` in the Ollama call.
**Why:** we want deterministic structured JSON output, not creative variation. Low temperature makes JSON parsing much more reliable and cache hits more consistent across re-runs.

### D-14 · JSON response parsing with prose-stripping fallback
**Decision:** find first `{` and last `}` in the raw response; parse that substring.
**Why:** LLMs often wrap JSON in prose ("Here is the JSON:") or markdown fences even when instructed not to. The substring extraction handles both cases without a more complex parser.
**Tradeoff:** fails on nested prose between chunks. Mitigated by the per-batch fallback (empty entity list, logged at WARNING).

### D-15 · rel_type allowlist in link_entities()
**Decision:** `link_entities()` validates `rel_type` against `{"RELATED_TO", "PART_OF"}` before string-concatenating it into Cypher.
**Why:** dynamic Cypher construction with user-supplied strings is a Cypher injection vector. Allowlist is the correct fix for a closed-world relationship type set.

### D-16 · Entity methods added to Neo4jHelper (neo4j_utils), not Neo4jManager
**Decision:** new entity methods go into `Neo4jHelper` in `neo4j_utils.py`, not into `Neo4jManager` in `neo4j_manager.py`.
**Why:** `Neo4jHelper` is the existing lower-level CRUD layer (`create_document`, `link_documents`, `create_topic_and_relationship`). `Neo4jManager` is the batch-import orchestrator. Entity operations are single-entity CRUD — they belong with `Neo4jHelper`. `extract_concepts.py` uses `Neo4jHelper` directly, consistent with how the rest of the codebase treats it.

---

## Part D — Auto-Relationship Inference

### D-17 · Manual related: edges resolved by file path, not doc ID
**Decision:** `import_documents()` builds a `path -> doc_id` map from the current batch and resolves `related:` values against it.
**Why:** frontmatter `related:` lists contain file paths (e.g., `your_docs_here/doc2.md`), not internal UUIDs. Resolving at import time within the same batch is free; resolving later would require an extra Neo4j round-trip.
**Tradeoff:** `related:` entries pointing to files not in the current import batch are silently skipped. Acceptable — cross-batch relationships will be created on re-import or via auto-link.

### D-18 · Category auto-assignment via majority vote across chunks
**Decision:** `extract_concepts.py` collects `suggested_category` per chunk, then picks the most-voted category per document to update Neo4j.
**Why:** a document's chunks may suggest different categories (introduction vs. conclusion may feel different topically). Majority vote is robust against noise in any single chunk's LLM response without needing a separate consolidation call.
**Tradeoff:** ties broken by Python dict ordering (first-seen wins). Acceptable at this scale.

### D-19 · D1 category suggestion piggybacked on extraction prompt, not a separate call
**Decision:** `suggested_category` is a third field added to the existing extraction JSON, not a new Ollama call.
**Why:** the plan explicitly specifies this: "one extra field in the JSON output, so it costs zero additional LLM calls". Extracting category separately would double LLM call count.

### D-20 · update_document_category() only updates 'uncategorized' docs
**Decision:** the Cypher in `update_document_category()` has a `WHERE d.category = 'uncategorized' OR d.category IS NULL` guard.
**Why:** if a doc has a manually-authored category in frontmatter, the auto-classification must not overwrite it. The guard ensures manual frontmatter is always the higher-confidence source.

### D-21 · Embedding-similarity linking loads vectors from Qdrant, not re-embeds
**Decision:** `fetch_all_doc_chunks_embeddings()` scrolls Qdrant for existing vectors and mean-pools them per document.
**Why:** re-embedding all documents just to compute pairwise similarity would re-run the embedding model unnecessarily. The vectors are already in Qdrant from `import_docs.py` — pulling them is the lazy (efficient) choice.
**Tradeoff:** mean-pooling is a crude doc-level representation vs. a proper document embedding. Sufficient for the threshold-based linking use case; a more expensive option would be to embed the full doc text separately.

### D-22 · auto_link_related_documents is a single Cypher + Python loop, not a batch endpoint
**Decision:** concept-overlap is one Cypher query; embedding-similarity is a nested Python loop with one session.run() per qualifying pair.
**Why:** concept-overlap can be expressed entirely in Cypher (MATCH + WITH + WHERE + MERGE). Embedding-similarity requires Python (numpy dot products) — Neo4j doesn't expose vector math natively without a GDS plugin. The loop is O(n^2) over document count, which is fine for small-medium corpora; for very large corpora a FAISS index would be the upgrade path. ponytail: O(n^2) scan — upgrade to FAISS if corpus > ~1000 docs.

### D-23 · --skip-auto-link flag on extract_concepts.py
**Decision:** `--skip-auto-link` lets the user run extraction only, without triggering the relationship inference pass.
**Why:** on first run you want to see extraction quality before trusting inferred relationships. Also useful for --doc-id incremental runs where a full graph re-scan would be premature.

---

## Part B3 â€” Concept Graph Query Expansion

### D-24 Â· expand_via_concepts() is a silent no-op when concept graph is empty
**Decision:** if `get_entities_for_chunks()` returns nothing (concept graph not populated yet), `expand_via_concepts()` returns [] immediately with no error.
**Why:** hybrid_search must remain functional even before `extract_concepts.py` has been run. The expansion is additive â€” its absence doesn't degrade the existing vector + graph-adjacency search.

### D-25 Â· Concept-expanded results get a lower weight band than graph-adjacent docs
**Decision:** score tiers: semantic (up to 0.7) > graph-adjacent (up to 0.5 * 0.3 = 0.15) > concept-expanded (up to 0.3 * 0.3 = 0.09).
**Why:** concept expansion is the most speculative path (entity â†’ related entity â†’ document) â€” highest false-positive risk. Keeping it below direct graph adjacency means it can only surface results that weren't already going to rank, without displacing confirmed relevant hits.

### D-26 Â· get_related_documents() now orders by via-priority (manual > shared_concepts > ...)
**Decision:** CASE expression in Cypher assigns numeric rank to via values; ORDER BY via_rank DESC, weight DESC.
**Why:** a manually-authored `related:` link is more reliable than a co-occurrence-inferred one. Surfacing manual links first means the query engine benefits from human curation when it exists, while still using auto-inferred links when it doesn't.

### D-27 — Entity overlap score normalised as overlap/max(overlap,5)
**Decision:** concept expansion score uses `overlap / max(overlap, 5)` as the entity-match fraction.
**Why:** avoids runaway scores when one doc shares many entities (e.g., overlap=20 would give 20/20=1.0 without the cap). The cap of 5 means "sharing 5+ entities is as good as sharing all of them" — a reasonable ceiling for a 3B model's extraction fidelity.

### D-28 — expansion field added to every result dict
**Decision:** each result in result_map carries an `expansion` field: "vector", "graph:manual", "graph:shared_concepts", or "concept".
**Why:** makes it trivial to debug which path surfaced a result (log it, filter it, display it). Zero cost to add, high debugging value.

---

### D-29 — Fixed _fixed_chunks tail loop termination
**Decision:** add `if end >= len(text): break` to `_fixed_chunks()`.
**Why:** when `len(text) - start` is smaller than `chunk_size`, `end` reaches `len(text)`. Without an explicit termination check, calculating `start = max(end - chunk_overlap, start + 1)` caused the pointer to creep forward by 1 character on every iteration until `start == len(text)`, emitting ~100 duplicate single-character-shifted chunks for every document tail.
**Tradeoff:** none — this was a critical algorithmic defect; fixing it dropped chunk counts from 1071 to 371 across the corpus and eliminated massive redundant embedding/Ollama inference.
