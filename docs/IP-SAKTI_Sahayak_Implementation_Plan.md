# IP-SAKTI Sahayak — Full Implementation Plan
## Adapting the existing `vignesh-poovanna/GraphRAG` repo into a multilingual, source-cited, agentic RAG assistant for Ayurveda IP & regulatory guidance

**SIH 2026 Problem Statement:** SIH26045, Ministry of AYUSH
**Base repository:** https://github.com/vignesh-poovanna/GraphRAG
**Execution tool:** Codex, editing the existing repo in place (not a rewrite)

---

## 0. Read-First Instructions for Codex

Before changing anything, read the following existing files in the repo — they contain prior architecture decisions and plans that must be respected or explicitly superseded, not silently overwritten:
- `docs/decisions.md` — architecture decision records. Any new decision in this plan that conflicts with an existing ADR must be logged as a new dated entry explaining the change, not a silent overwrite.
- `docs/flow.md` — the current pipeline flow documentation. Update this file at the end of each phase below to reflect what changed.
- `docs/graphrag-hybrid-plan.md` — the original system's extension/spec plan. Cross-check this plan against it; where they overlap, treat the older plan as superseded by this document but preserve any technical constraints it documents (e.g. why certain design choices were made).
- `docs/visualization_guide.md` — Cypher queries and visualization instructions; extend, don't replace, when adding new node/edge types.
- `guides/` folder — read every file here; it likely contains operational how-tos for running/extending the pipeline that this plan's phases depend on. If any guide conflicts with a step below, follow the guide's operational detail and flag the conflict in the phase's completion notes.
- `AGENTS.md` and `AI_ENTRY.md` — these appear to be existing instructions for AI coding agents working on this repo. Follow them as the outer operating rules for every phase below; this plan works within them, not around them.

Do this read as literal Phase 0 before writing any code.

---

## 1. Problem Statement, Restated Precisely

Ayurveda's intellectual property sits at the intersection of three things that don't naturally talk to each other:
1. A huge, fragmented body of **traditional knowledge (TK)** — classical texts, community-held formulations, TKDL-style records — much of it not in English.
2. **National IP law** — Indian Patents Act, Biological Diversity Act, Geographical Indications Act, AYUSH-specific regulatory rules.
3. **International IP regimes** — WIPO frameworks, the Nagoya Protocol on genetic resource access/benefit-sharing, and individual foreign patent offices' rules (USPTO, EPO, etc.) on prior art and patentability.

Right now, anyone trying to answer a real question ("can I patent this formulation," "does this infringe on documented TK," "what does the EU require for GI registration of this product") has to manually cross-reference all three, often in different languages, with no single trustworthy source.

**What must be built:** a multilingual conversational AI assistant that retrieves from all three categories of source material, reasons across them when a question requires more than one lookup, and always shows exactly which document/section its answer came from — because an answer that "sounds right" but can't be traced back to a real legal source is actively dangerous in this domain.

**What must NOT happen:** the assistant must never present an answer with unstated confidence when the underlying law is genuinely ambiguous or jurisdiction-dependent, and it must never let the LLM answer from general training knowledge instead of the retrieved corpus — this second point is already enforced in the existing repo's `generate_answer()` guardrail, which is a major head start.

---

## 2. What We're Reusing vs. Changing vs. Building New

| Category | Component | Status |
|---|---|---|
| **Reuse as-is** | Qdrant vector store + Neo4j graph store, dual-database architecture | Keep |
| **Reuse as-is** | Boundary-aware chunking (`document_processor.py`) | Keep |
| **Reuse as-is** | Grounded-answer refusal guardrail in `generate_answer()` | Keep — this is core to the "source-cited" requirement |
| **Reuse as-is** | Docker Compose orchestration for Neo4j + Qdrant | Keep |
| **Reuse as-is** | SQLite concept-cache for idempotent extraction | Keep |
| **Modify** | `concept_extractor.py` — entity/relation schema | Rewrite prompts and schema for IP/Ayurveda domain |
| **Modify** | `embedding_processor.py` — embedding model | Swap to multilingual model |
| **Modify** | `format_converter.py` / ingestion metadata | Add jurisdiction, act name, section number, language fields |
| **Modify** | `query_engine.py` — retrieval logic | Extend into multi-step agentic orchestration |
| **Modify** | LLM backend (`Ollama llama3.2:3b`) | Keep for local extraction; add stronger model option for final answer generation |
| **Build new** | Multilingual query handling layer | Query translation/embedding alignment |
| **Build new** | Speech-to-speech pipeline (STT + TTS + barge-in) | Already on your own roadmap — now scheduled |
| **Build new** | Web frontend (chat UI + reasoning trace + citations) | Currently CLI-only (`query_demo.py`) |
| **Build new** | Legal citation formatter | New metadata-to-citation rendering layer |
| **Build new** | Novelty/prior-art pre-check feature | New retrieval mode built on existing hybrid search |
| **Build new** | Multi-jurisdiction comparison mode | New agentic query pattern |

---

## PHASE 1 — Corpus Definition & Acquisition

**Goal:** Replace `your_docs_here/` with the actual regulatory/TK corpus, fully tagged with source metadata.

**Sources to acquire (all public):**
- Indian Patents Act, 1970 (as amended) — full text, section-numbered
- Biological Diversity Act, 2002 — full text
- Geographical Indications of Goods (Registration and Protection) Act, 1999
- AYUSH-specific regulatory notifications (Ministry of AYUSH official gazette)
- TKDL public-facing documentation (structure/classification system — TKRC) — note TKDL's actual formulation database is access-restricted to patent offices, so use its published methodology and publicly available case outcomes, not the restricted database itself
- WIPO IGC (Intergovernmental Committee on IP and Genetic Resources, TK and Folklore) published documents
- Nagoya Protocol full text
- USPTO and EPO's public guidance on prior art and patentability as applied to traditional medicine (published examination guidelines)
- Published case law: the turmeric patent revocation, the neem patent case, and any other publicly documented Ayurveda-related IP disputes — these are essential for the "case law/precedent lookup" feature discussed earlier
- Sample Ayurveda pharmacopoeia texts (API — Ayurvedic Pharmacopoeia of India) for grounding formulation-related questions

**Task for Codex:**
1. Create `data/input/` subfolders by category: `national_law/`, `international_law/`, `case_law/`, `pharmacopoeia/`, `tkdl_methodology/`.
2. For every document, create a companion metadata sidecar (or embed as front-matter if markdown) capturing: `jurisdiction`, `act_or_source_name`, `year`, `language`, `document_type` (statute / case / guideline / pharmacopoeia). This metadata is what powers Phase 5's citation formatting — do not skip it.
3. Where a source is only available in a non-English language (e.g., Sanskrit-origin texts), store the original AND a translated version, both metadata-tagged with `language`, so retrieval can serve either.

---

## PHASE 2 — Domain Schema Redesign (the most important structural change)

**Goal:** Rewrite what `concept_extractor.py` treats as an "entity" and "relation," since the current schema (technical components/states/parameters) doesn't map to legal/Ayurveda content at all.

**New entity types to extract:**
- `Formulation` (e.g., a named Ayurvedic preparation)
- `Ingredient` (plant/mineral/animal-derived substance)
- `LegalInstrument` (a specific Act, Section, Rule, or Treaty)
- `Jurisdiction` (country or regional body — India, EU, US, WIPO)
- `IPProtectionType` (Patent, GI, Traditional Knowledge record, Trade Secret)
- `CasePrecedent` (a specific dispute/ruling, e.g. "Turmeric Wound-Healing Patent Revocation")
- `RegulatoryBody` (USPTO, EPO, Indian Patent Office, Ministry of AYUSH, CSIR-TKDL)

**New relation types:**
- `(:Formulation)-[:CONTAINS_INGREDIENT]->(:Ingredient)`
- `(:Formulation)-[:DOCUMENTED_IN]->(:LegalInstrument or CasePrecedent)`
- `(:LegalInstrument)-[:APPLIES_IN]->(:Jurisdiction)`
- `(:CasePrecedent)-[:CITES]->(:LegalInstrument)`
- `(:IPProtectionType)-[:GOVERNED_BY]->(:LegalInstrument)`
- `(:Formulation)-[:ELIGIBLE_FOR]->(:IPProtectionType)` (model-inferred, must be flagged as inference not fact — see Phase 6 on confidence flagging)

**Task for Codex:**
1. Rewrite the extraction prompt template inside `concept_extractor.py` to describe this schema explicitly to the local LLM (`llama3.2:3b`), with few-shot examples drawn from 2–3 real chunks from Phase 1's corpus (e.g., an example extraction from the Biological Diversity Act text).
2. Extend `neo4j_manager.py`'s schema-writing functions to support these new node/relationship labels alongside the existing generic `Entity`/`RELATED_TO` types (don't delete the generic types — some content, like pharmacopoeia entries, may still be best captured generically).
3. Update `docs/visualization_guide.md` with new Cypher query examples for the new schema (e.g., "show all formulations connected to a given legal instrument").
4. Re-run extraction cache invalidation logic in `concept_cache.db` since the schema change means old cached extractions are now stale — document this explicitly so Codex doesn't silently reuse outdated cache entries.

---

## PHASE 3 — Multilingual Embedding & Retrieval

**Goal:** A query in Hindi (or another Indian language) must retrieve the correct chunk even when the source document is in English legal text, and vice versa.

**Task for Codex:**
1. Swap `all-MiniLM-L6-v2` in `embedding_processor.py` for a multilingual sentence-embedding model with strong Indian-language coverage — e.g., `intfloat/multilingual-e5-large` or `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`. Note the dimension change (from 384-dim) — this requires reinitializing the Qdrant collection schema (`qdrant_manager.py`), not just swapping the model in place, since vector dimensions must match the collection config.
2. Re-embed the entire corpus after the model swap — old 384-dim vectors are incompatible and must be regenerated, not migrated.
3. Add a lightweight query-language detection step before retrieval (a simple langid library call is sufficient) so downstream logic (e.g., which language to render citations/answers in) knows the user's language without requiring an explicit toggle.
4. Test retrieval quality specifically cross-lingually: write at least 10 test queries in Hindi/regional language that should retrieve English-source legal chunks, and confirm retrieval rank quality before moving on — this is a common silent-failure point, don't skip validation.

---

## PHASE 4 — Citation & Metadata Rendering Layer

**Goal:** Turn the existing "here's the chunk/document it came from" citation into a proper legal-style citation, using the metadata captured in Phase 1.

**Task for Codex:**
1. Extend the chunk payload structure in `qdrant_manager.py` and the `Chunk` node properties in `neo4j_manager.py` to carry the full metadata sidecar from Phase 1 (`jurisdiction`, `act_or_source_name`, `section`, `year`, `document_type`).
2. Build a `citation_formatter.py` module in `src/utils/` that takes a retrieved chunk's metadata and renders a proper citation string, e.g.: `"Biological Diversity Act, 2002, Section 3 (India)"` or `"Turmeric Wound-Healing Patent Revocation, USPTO, 1997"`.
3. Update `generate_answer()` in `query_engine.py` so every answer's supporting chunks are rendered through `citation_formatter.py` before being returned, not just as raw filenames.
4. This citation data is also what will power the frontend's "clickable document provenance" feature from your own roadmap — structure the output as a list of `{claim_text, citation, source_snippet}` objects so the frontend can render them as inline references, not a flat text blob.

---

## PHASE 5 — Agentic RAG Orchestration Layer

**Goal:** Move from "one retrieval pass → one generation pass" to genuine multi-step reasoning for questions that require checking more than one source category before answering.

**Task for Codex:**
1. Create a new module `src/agent/orchestrator.py` that sits above `query_engine.py`. It should:
   - Take the user's question and classify its type (novelty-check / jurisdiction-comparison / general-lookup / precedent-lookup) — a simple LLM-based classification prompt is sufficient here.
   - For a **novelty-check** question: run `hybrid_search()` against the TKDL-methodology + pharmacopoeia + case-law categories first, then only fall back to statute text if no prior-art match is found.
   - For a **jurisdiction-comparison** question: run `hybrid_search()` once per detected jurisdiction (India, US, EU, WIPO) using the same underlying question, then assemble the results into a structured comparison rather than a single blended answer.
   - For a **precedent-lookup** question: prioritize `CasePrecedent` nodes and their `CITES` relations via graph traversal before vector search.
   - For a **general-lookup** question: fall back to the existing single-pass `generate_answer()` behavior unchanged.
2. Each orchestration step's tool calls should be logged into a structured trace object (list of `{step, query_used, source_category, chunks_retrieved}`) — this is what will power the "reasoning trace" UI feature discussed earlier, and it directly serves the "agentic RAG" requirement from your own feature list.
3. Keep the existing guardrail intact at the final synthesis step: even in multi-step mode, the final answer generation must still refuse to state anything not grounded in retrieved chunks across all steps combined.

---

## PHASE 6 — Confidence Flagging & Ambiguity Handling

**Goal:** The assistant must distinguish between "the law clearly says X" and "this is genuinely unsettled or jurisdiction-dependent."

**Task for Codex:**
1. In the final synthesis prompt (inside `generate_answer()` or the new orchestrator), add an explicit instruction requiring the LLM to tag each claim as either `[CLEAR]` (directly stated in a retrieved source) or `[AMBIGUOUS/JURISDICTION-DEPENDENT]` (inferred, conflicting across sources, or not explicitly addressed).
2. Parse these tags in a post-processing step and render them visibly in the output — e.g., ambiguous claims get a distinct visual treatment in the frontend (Phase 9) rather than being presented identically to clear-cut answers.
3. Any `ELIGIBLE_FOR` relationship from Phase 2's schema (which is inherently model-inferred, not a stated legal fact) must always be surfaced with an `[INFERRED]` tag and a pointer to a human-expert escalation note — do not let inferred eligibility read as a legal determination.

---

## PHASE 7 — LLM Backend Strategy

**Goal:** Keep the cheap local model for high-volume extraction work, but use a stronger model where legal reasoning quality actually matters.

**Task for Codex:**
1. Keep `Ollama llama3.2:3b` for Phase 2's concept/entity extraction — this is high-volume, low-stakes (structural extraction, not final legal answers), and the existing SQLite caching keeps it cheap.
2. Add a configurable LLM backend for the final answer-generation step in `generate_answer()` and the orchestrator — support swapping to a stronger hosted model via API for this step specifically, since cross-jurisdiction legal reasoning benefits from a stronger model. Keep the local model as a fallback/offline option so the "sovereign, on-prem" angle (relevant to Ministry of AYUSH's likely data-sensitivity concerns) is still available.
3. Update `config.py` to expose this as an explicit `EXTRACTION_LLM` vs `SYNTHESIS_LLM` split rather than one hardcoded model reference.

---

## PHASE 8 — Speech-to-Speech with Smart Interruption

**Goal:** Execute the voice roadmap item already documented in the repo.

**Task for Codex:**
1. Add a streaming STT layer (Whisper, local or API) that converts user speech to text in their spoken language, feeding into the multilingual query pipeline from Phase 3.
2. Add a low-latency TTS layer that speaks the final answer back in the same language — note that a translated/localized version of the citation formatting from Phase 4 is needed so citations are spoken naturally, not read as a raw text string.
3. Implement barge-in detection: while TTS is playing, continuously run a lightweight voice-activity-detection (VAD) check on the microphone input; on detecting new user speech, immediately halt TTS playback and begin a new STT capture — this is the "smart interruption" feature. A standard approach is Silero VAD or WebRTC VAD running client-side, triggering an interrupt signal to the TTS playback process.
4. Preserve session context across an interruption — the new user utterance should be treated as a follow-up within the same orchestrator session (Phase 5), not a fresh conversation, so a mid-answer interruption to refine a jurisdiction or add a constraint doesn't lose prior context.

---

## PHASE 9 — Frontend / Dashboard

**Goal:** Move off the CLI (`query_demo.py`) onto a real interface with the dual-channel interaction style from your own roadmap.

**Task for Codex:**
1. Build a **React** frontend (framework choice matches your prior project's direction and avoids Streamlit).
2. Core screens:
   - **Chat interface** — text and voice input toggle, streaming response display.
   - **Reasoning trace panel** — renders the orchestrator's step log from Phase 5 (which source category was checked, in what order) as a collapsible sidebar, so the user can audit how the answer was constructed.
   - **Citation panel** — each claim in the response is clickable, expanding to show the exact source snippet and full citation from Phase 4.
   - **Ambiguity indicators** — visually distinct styling for `[AMBIGUOUS]` vs `[CLEAR]` vs `[INFERRED]` tagged claims from Phase 6.
   - **Jurisdiction comparison view** — when the orchestrator runs a multi-jurisdiction query, render results as a side-by-side table rather than blended prose.
3. Backend API: wrap the orchestrator (`src/agent/orchestrator.py`) and `query_engine.py` in a FastAPI service exposing endpoints for text query, voice stream, and trace retrieval — this mirrors the MCP/JSON-RPC "agent-to-agent" interface already planned in the repo's roadmap, so implement the human-facing REST API and the MCP tool interface as two thin wrappers around the same orchestrator core, not two separate implementations.

---

## PHASE 10 — Testing & Validation

**Goal:** Confirm the domain adaptation actually works before treating any phase as done.

**Task for Codex:**
1. Extend `test_hallucination.py` with domain-specific edge cases: ask questions where the correct answer is "the corpus does not address this" and confirm the refusal guardrail still fires correctly after all the schema/model changes.
2. Build a small labeled test set (15–20 question/expected-citation pairs) covering: a clear-cut national law question, a clear-cut international question, a genuinely ambiguous cross-jurisdiction question, and a known case-precedent question (e.g., "was the neem patent revoked, and under what basis"). Run this set after every major phase to catch regressions.
3. Cross-lingual test set from Phase 3 — re-run after every embedding-affecting change.
4. Manually verify at least 5 full agentic traces (Phase 5) to confirm the orchestrator is actually querying multiple categories when it should, not silently falling back to single-pass retrieval.

---

## PHASE 11 — Documentation & Handoff

**Goal:** Leave the repo in a state where the architecture decisions are traceable, matching the existing repo's own documentation discipline.

**Task for Codex:**
1. Add new dated entries to `docs/decisions.md` for every major architectural change in this plan (embedding model swap, schema redesign, agentic layer addition, LLM backend split).
2. Update `docs/flow.md` with the new end-to-end pipeline diagram reflecting the orchestrator layer and multilingual/voice additions.
3. Update the root `README.md`'s "Roadmap and Future Work" section — the voice/interruption item moves from roadmap to "implemented," and add any genuinely deferred features (e.g., biopiracy watch/alerts, WhatsApp access) as the new roadmap.
4. Update `AGENTS.md`/`AI_ENTRY.md` if any of this plan's phases change the operating constraints future AI coding agents should follow on this repo.

---

## Known Risks to Flag Explicitly (do not omit from final deliverable)

- TKDL's actual formulation database is access-restricted to patent offices under non-disclosure agreements — this system cannot legally ingest that restricted database directly; it must rely on publicly available TKDL methodology, published case outcomes, and open-source pharmacopoeia texts instead. State this limitation clearly rather than implying full TKDL integration.
- The `ELIGIBLE_FOR` relationship and any model-inferred eligibility claim is never a legal determination — this must be enforced through Phase 6's tagging at every layer, including voice output, or the system risks giving false confidence on high-stakes IP decisions.
- Multilingual retrieval quality depends heavily on the chosen embedding model's actual training coverage of Indian languages — validate this empirically (Phase 3, step 4) rather than assuming a multilingual-labeled model performs well on the specific languages needed.
- Re-embedding the corpus after the Phase 3 model swap is a one-time but non-trivial cost — schedule it deliberately, don't let it silently block later phases.
