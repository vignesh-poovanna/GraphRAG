# flow.md — Execution Flow

Complete call-graph of what calls what, in order, for every major path.

---

## 1. Document Import (`python scripts/import_docs.py`)

```
import_docs.py :: main()
  |
  |-- Config()                              # src/config.py — loads .env, builds config dict
  |-- Neo4jManager(config).connect()        # src/database/neo4j_manager.py
  |-- EmbeddingProcessor(config).load_model()  # src/processors/embedding_processor.py
  |-- QdrantManager(config, emb_proc).connect()
  |
  |-- neo4j_manager.setup_schema()          # runs CREATE CONSTRAINT ... queries
  |-- [optional] neo4j_manager.clear_database()
  |-- qdrant_manager.create_collection()
  |
  |-- FormatConverter()                     # src/processors/format_converter.py
  |-- DocumentProcessor(config)             # src/processors/document_processor.py
  |
  |-- for each file in docs_dir:
  |     |
  |     |-- [.md] DocumentProcessor.process_document(file_path, source_type="md")
  |     |         |-- _extract_front_matter(text)   -> (metadata, body)
  |     |         |-- _chunk_text(body)
  |     |         |     |-- [strategy=structure_aware] _structure_aware_chunks(body)
  |     |         |     |     line-walk state machine:
  |     |         |     |       tracks in_code / in_table state
  |     |         |     |       flushes on heading (##/###)
  |     |         |     |       flush() -> sub-splits via _fixed_chunks() if oversized
  |     |         |     |-- [strategy=fixed] _fixed_chunks(body)
  |     |         |-- returns (metadata, [chunk_objects])
  |     |
  |     |-- [non-.md] FormatConverter.convert(file_path)
  |     |         |-- ext dispatch:
  |     |         |     .pdf  -> _convert_pdf()  -> docling.DocumentConverter (lazy import)
  |     |         |     .docx -> _convert_docx() -> markitdown.MarkItDown (lazy import)
  |     |         |     .html -> _convert_html() -> trafilatura.extract (lazy import)
  |     |         |     .txt  -> _convert_txt()  -> plain read
  |     |         |-- _ensure_frontmatter(md, filepath) -> injects YAML if missing
  |     |         |-- returns (markdown_text, source_type)
  |     |     then DocumentProcessor.process_document(path, text=md_text, source_type=...)
  |
  |-- Neo4jManager.import_documents(docs, chunks)
  |     |-- _create_documents_batch(session, batch)  UNWIND -> MERGE Document
  |     |-- _create_chunks_batch(session, batch)     UNWIND -> MERGE Chunk + HAS_CHUNK + NEXT
  |     |-- MERGE RELATED_TO {via:'shared_category'} for same-category docs
  |     |-- for each doc with related: frontmatter:
  |           MERGE RELATED_TO {via:'manual'} edges
  |
  |-- QdrantManager.import_chunks(chunks)
  |     |-- for each chunk:
  |     |     EmbeddingProcessor.get_embedding(chunk.text) -> vector[384]
  |     |     build payload: {text, doc_id, position, source_type, chunk_type, ...metadata}
  |     |     batch into PointStruct, upsert every 100
  |
  |-- neo4j_manager.get_statistics()
  |-- qdrant_manager.get_statistics()
  |-- neo4j_manager.close() / qdrant_manager.close() / emb_proc.unload_model()
```

---

## 2. Concept Extraction (`python scripts/extract_concepts.py`)

```
extract_concepts.py :: main()
  |
  |-- ConceptExtractor(model, host, cache_path, batch_size)
  |     |-- sqlite3.connect(cache_path)
  |     |     CREATE TABLE IF NOT EXISTS cache (hash TEXT PRIMARY KEY, result TEXT)
  |
  |-- extractor.is_available()             # GET http://localhost:11434 via ollama.Client
  |
  |-- Config() + Neo4jHelper(uri, user, pw)
  |-- helper.verify_connection()           # RETURN 'Connection successful'
  |
  |-- fetch_chunks(helper, doc_id=...)
  |     MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
  |     RETURN c.id, c.text, d.id, d.category
  |
  |-- for batch in chunks[0::batch_size]:
  |     ConceptExtractor.extract_batch(batch)
  |       |-- for each chunk: SHA-256(text) -> check SQLite cache
  |       |-- uncached chunks -> _process_uncached_batch()
  |       |       |-- _build_prompt(chunks)     # one prompt, N chunk texts + category ask
  |       |       |-- _call_ollama(prompt)
  |       |       |     ollama.Client.generate(model, prompt, temperature=0.0)
  |       |       |-- _parse_response(raw, chunks)
  |       |       |     strip fences, find {}, json.loads(), normalise per chunk_id
  |       |       |-- cache.INSERT OR REPLACE (hash, json)
  |       |-- returns {chunk_id: {entities, relationships, suggested_category}}
  |
  |     [not dry_run] write_concepts(helper, chunk_id, extraction)
  |       |-- for each entity:
  |       |     helper.create_entity(name, type)     MERGE (:Entity {name})
  |       |     helper.link_chunk_to_entity(cid, name)  MERGE (:Chunk)-[:MENTIONS]->(:Entity)
  |       |-- for each relationship:
  |             helper.link_entities(src, tgt)    MERGE (:Entity)-[:RELATED_TO]->(:Entity)
  |
  |     collect suggested_category votes per doc_id
  |
  |-- [D1] for each doc with uncategorized category:
  |     majority_vote = max(votes)
  |     helper.update_document_category(doc_id, majority_vote)
  |         MATCH (d:Document {id}) WHERE d.category='uncategorized' SET d.category=...
  |
  |-- [D2, if not --skip-auto-link and not --doc-id]
  |     fetch_all_doc_chunks_embeddings(helper)
  |       |-- QdrantManager.scroll(collection, with_vectors=True)  [paginated]
  |       |-- np.mean(vectors_per_doc) -> {doc_id: np.array[384]}
  |
  |     helper.auto_link_related_documents(min_shared, threshold, doc_embeddings)
  |       |-- [concept-overlap] Cypher:
  |       |     MATCH (d1)-[:HAS_CHUNK]->(c1)-[:MENTIONS]->(e)<-[:MENTIONS]-(c2)<-[:HAS_CHUNK]-(d2)
  |       |     WHERE d1.id < d2.id  WITH count(DISTINCT e) AS shared  WHERE shared >= N
  |       |     MERGE (d1)-[r:RELATED_TO {via:'shared_concepts'}]->(d2)  SET r.weight=shared
  |       |
  |       |-- [embedding-similarity] Python loop:
  |             L2-normalise all doc vectors
  |             for each pair (i,j): cosine_sim = dot(vi, vj)
  |             if sim >= threshold:
  |               MERGE (d1)-[r:RELATED_TO {via:'embedding_similarity'}]->(d2) SET r.weight=sim
  |
  |-- helper.close()
```

---

## 3. Query Engine (`src/query_engine.py`) — unchanged by Parts A-D

> Query engine changes are Part B3 (last step). The existing flow is untouched.

Current flow for reference:
```
GraphRAGQuery.search(query, search_type, category_filter, limit)
  |-- EmbeddingProcessor.get_embedding(query)
  |-- QdrantManager.search(query_text, limit, filter)  -> vector results
  |-- Neo4jManager.expand_context(doc_ids)             -> graph-expanded docs
  |-- rank_results(vector_results + graph_results)
  |-- return ranked list
```

---

## 4. Neo4j Schema (node/relationship types in use after all parts)

```
(:Document)         id, title, category, path, source_type
  -[:RELATED_TO {via, weight}]->  (:Document)
      via values: "manual" | "shared_category" | "shared_concepts" | "embedding_similarity"

(:Document)-[:HAS_CHUNK]->(:Chunk)
  Chunk: id, text, position, source_type, chunk_type

(:Chunk)-[:NEXT]->(:Chunk)         sequential chain

(:Chunk)-[:MENTIONS]->(:Entity)
  Entity: name, entity_type

(:Entity)-[:RELATED_TO {weight}]->(:Entity)
(:Entity)-[:PART_OF]->(:Entity)        (optional hierarchy)

(:Document)-[:HAS_TOPIC]->(:Topic)     (existing, from original repo)
```

---

## 5. Config resolution order

```
.env file (loaded by dotenv)
  -> Config.__init__() sets defaults (neo4j.*, qdrant.*, embedding.*, chunking.*)
  -> os.getenv() overrides defaults
  -> Optional YAML file overrides via _update_dict()
  -> Module-level exports: NEO4J_URI, CHUNKING_STRATEGY, MAX_CHUNK_SIZE, etc.
```

---

## 6. Key design invariant: FormatConverter is a one-way normalization gate

```
Any file type
  -> FormatConverter.convert()        # always outputs (markdown_str, source_type)
  -> DocumentProcessor.process_document(path, text=markdown_str, source_type=...)
  -> Neo4j + Qdrant storage (unchanged)
```


The downstream pipeline never sees raw PDF/HTML/DOCX bytes.
CHUNKING_STRATEGY=fixed bypasses structure-aware logic at DocumentProcessor._chunk_text().

---

## IP-SAKTI Sahayak — Query Flow (Phases 5–9)

```
User input (text or voice)
  |
  |-- [Voice] SpeechPipeline._record_until_silence()
  |           VAD (silero or energy) → float32 numpy array
  |           SpeechPipeline._transcribe()  # faster-whisper WhisperModel
  |
  |-- SpeechPipeline._maybe_translate()     # langdetect → Groq translate if non-EN
  |
  |-- SessionCache.get_history(session_id, last_n=4)   # SQLite
  |
  |-- Orchestrator.run(query, session_context=history)
  |     |
  |     |-- Orchestrator._classify_query()
  |     |     Cerebras API (llama3.1-8b) → one of:
  |     |       novelty_check | jurisdiction_comparison | precedent_lookup | procedural | general
  |     |
  |     |-- [novelty_check]
  |     |     for cat in [ip/tkdl_methodology, ip/pharmacopoeia, ip/case_law]:
  |     |       QueryEngine.hybrid_search(query, limit=3, category=cat)
  |     |         → Qdrant vector search (query: prefix, multilingual-e5-large)
  |     |         → Neo4j graph-adjacent doc expansion
  |     |         → Concept-graph expansion (Entity→MENTIONS→Chunk)
  |     |         → merge + rerank by final_score
  |     |
  |     |-- [precedent_lookup]
  |     |     Neo4jManager.get_case_precedents_for_instrument(keyword) per keyword
  |     |     QueryEngine.hybrid_search(query, category=ip/case_law)
  |     |
  |     |-- [jurisdiction_comparison]
  |     |     Orchestrator._detect_export_route()   # supplement vs drug keyword check
  |     |     for jur in [India, US, EU, ...]:
  |     |       Neo4jManager.get_instruments_for_jurisdiction(jur)
  |     |       QueryEngine.hybrid_search(f"{query} {jur}", category=...)
  |     |
  |     |-- [procedural]
  |     |     QueryEngine.hybrid_search per [ip/manufacturing_licensing, ip/export_compliance]
  |     |     sort by chunk.metadata.stage using _STAGE_ORDER
  |     |     build numbered answer directly (no extra LLM call)
  |     |
  |     |-- [general]
  |           QueryEngine.generate_answer() → single-pass
  |
  |-- Orchestrator._synthesise(query, chunks, mode, ...)
  |     |
  |     |-- Build context string from top-6 chunks
  |     |-- [Phase 8] prepend session_context (last 4 turns)
  |     |-- Groq API (llama-3.1-8b-instant) → answer with [CLEAR]/[AMBIGUOUS]/[INFERRED] tags
  |     |-- verifier.verify_and_downgrade()    # string-overlap; no LLM call
  |     |-- citation_index.enrich_with_url()   # TSV lookup; no LLM call
  |     |-- return {answer, sources, trace, mode, language, tags}
  |
  |-- SessionCache.add_turn(session_id, "assistant", answer)
  |
  |-- [Voice] SpeechPipeline._speak(answer)
        sentence-split → kokoro-onnx TTS → sounddevice playback
        _barge_in_listener() in background thread (silero VAD)
        → if interrupt: SessionCache.save_interruption(); stop playback
```

## IP-SAKTI Sahayak — Ingestion Flow (Phase 1–3)

```
data/input/<category>/<file>.[pdf|docx|md|txt|html]
  |
  |-- FormatConverter.convert()
  |     _ensure_frontmatter(): injects jurisdiction, act_or_source_name, year,
  |                             language, document_type, stage from folder path
  |     PDF → docling/pdfminer → markdown
  |
  |-- DocumentProcessor.process_document()
  |     _extract_front_matter() → metadata dict
  |     _structure_aware_chunks():
  |       split on ## / ### headings
  |       protect tables/code blocks
  |       sub-split oversized sections (chunk_size=600, overlap=100)
  |
  |-- EmbeddingProcessor.get_embedding(chunk_text, mode='passage')
  |     "passage: " + text → intfloat/multilingual-e5-large → 1024-dim vector
  |
  |-- QdrantManager.import_chunks()    # upsert vector + full metadata payload
  |
  |-- [optional] extract_concepts.py
        ConceptExtractor (Ollama llama3.2:3b) → domain entities + relations
        Neo4jManager.upsert_domain_entity() / link_domain_relation()
        Neo4jManager.upsert_inferred_relation() for ELIGIBLE_FOR claims
```


