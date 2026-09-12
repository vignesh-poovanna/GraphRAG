"""
orchestrator.py — Phase 5 (IP-SAKTI Sahayak)

Agentic RAG orchestrator that sits above query_engine.QueryEngine.
Classifies the user's question into one of five modes and performs
multi-step retrieval before synthesis:

  novelty_check          — prior-art check (TKDL + pharmacopoeia + case_law first)
  jurisdiction_comparison — parallel retrieval per detected jurisdiction
  precedent_lookup        — CasePrecedent graph traversal + vector search
  procedural              — licensing/export step-by-step (Patch v1.1: stage ordering)
  general                 — single-pass fallback (existing generate_answer behaviour)

Every step is logged into a structured trace list so the UI can render the
reasoning trace panel (Phase 9).
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Jurisdictions the orchestrator can detect for multi-jurisdiction comparison
_JURISDICTIONS = ["India", "US", "EU", "WIPO", "International"]

# Category filters for each mode's primary retrieval pass
_NOVELTY_CATEGORIES = ["ip/tkdl_methodology", "ip/pharmacopoeia", "ip/case_law"]
_PROCEDURAL_CATEGORIES = ["ip/manufacturing_licensing", "ip/export_compliance"]

# Procedural stage order (Patch v1.1)
_STAGE_ORDER = ["application", "documentation", "inspection", "certification", "renewal", "penalty"]


class Orchestrator:
    """
    Multi-step agentic RAG orchestrator for IP-SAKTI Sahayak.

    Usage:
        orch = Orchestrator(query_engine, config)
        result = orch.run("Can I patent this Chyawanprash formulation?")
        # result["answer"], result["sources"], result["trace"], result["mode"]
    """

    def __init__(self, query_engine, config):
        """
        Args:
            query_engine: QueryEngine instance (already connected)
            config:       Config instance (for llm.* settings)
        """
        self.qe = query_engine
        self.config = config
        self._extraction_model = config.get("llm.extraction_model", "llama3.2:3b")
        self._synthesis_model  = config.get("llm.synthesis_model",  "llama-3.1-8b-instant")
        self._ollama_host      = config.get("llm.ollama_host", "http://localhost:11434")
        # Synthesis API (Groq)
        self._synthesis_api_key  = config.get("llm.synthesis_api_key", "")
        self._synthesis_base_url = config.get("llm.synthesis_base_url", "https://api.groq.com/openai/v1")
        # Classification API (Cerebras — fast, low token count)
        self._classify_model    = config.get("llm.classification_model", "llama3.1-8b")
        self._classify_api_key  = config.get("llm.classification_api_key", "")
        self._classify_base_url = config.get("llm.classification_base_url", "https://api.cerebras.ai/v1")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, query: str, session_context: list = None) -> dict:
        """
        Classify the query, run the appropriate multi-step retrieval,
        and synthesise a grounded answer.

        Args:
            query:           user question string
            session_context: list of prior {role, content} turns (for continuity
                             across interruptions — Phase 8 requirement)

        Returns:
            {
              "answer":   str,
              "sources":  list of citation objects,
              "trace":    list of step dicts,
              "mode":     str,
              "language": str,
              "tags":     list of confidence tags found in the answer
            }
        """
        trace = []
        language = self._detect_language(query)

        mode = self._classify_query(query, trace)
        trace.append({"step": "classify", "mode": mode, "query": query})

        if mode == "novelty_check":
            chunks = self._novelty_check(query, trace)
        elif mode == "jurisdiction_comparison":
            return self._jurisdiction_comparison(query, trace, language)
        elif mode == "precedent_lookup":
            chunks = self._precedent_lookup(query, trace)
        elif mode == "procedural":
            return self._procedural(query, trace, language)
        else:
            # general: delegate entirely to query_engine.generate_answer
            result = self.qe.generate_answer(query, language=language)
            result["trace"] = trace + [{"step": "general_lookup", "note": "single-pass"}]
            result["mode"] = "general"
            return result

        # Final synthesis for novelty_check and precedent_lookup
        return self._synthesise(query, chunks, mode, trace, language,
                                session_context=session_context)

    # ------------------------------------------------------------------
    # Query classification
    # ------------------------------------------------------------------

    def _classify_query(self, query: str, trace: list) -> str:
        """
        Classify the query into one of 5 modes.
        Uses Cerebras (fast, low-latency) when API key is set; falls back to local Ollama.
        """
        prompt = f"""Classify this legal/regulatory query into exactly one category:
- novelty_check: asks whether a formulation/ingredient is novel, patentable, or has prior art
- jurisdiction_comparison: asks for comparison across countries/legal systems (India vs US, EU requirements, etc.)
- precedent_lookup: asks about a specific legal case, ruling, or precedent
- procedural: asks how to obtain a license, register, apply, file, or follow a regulatory process
- general: any other regulatory or IP question

Query: {query}

Reply with ONLY the category name, nothing else."""

        mode = "general"
        try:
            if self._classify_api_key:
                from openai import OpenAI
                client = OpenAI(api_key=self._classify_api_key, base_url=self._classify_base_url)
                resp = client.chat.completions.create(
                    model=self._classify_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=10,
                )
                raw = resp.choices[0].message.content.strip().lower().split()[0]
            else:
                import ollama
                client = ollama.Client(host=self._ollama_host)
                resp = client.generate(
                    model=self._extraction_model,
                    prompt=prompt,
                    options={"temperature": 0.0, "num_predict": 10},
                )
                raw = resp.get("response", "").strip().lower().split()[0]

            if raw in {"novelty_check", "jurisdiction_comparison",
                       "precedent_lookup", "procedural", "general"}:
                mode = raw
        except Exception as e:
            logger.warning("Query classification failed (%s); defaulting to general", e)

        trace.append({"step": "classify_llm", "mode": mode, "backend": "cerebras" if self._classify_api_key else "ollama"})
        return mode

    # ------------------------------------------------------------------
    # Mode handlers
    # ------------------------------------------------------------------

    def _novelty_check(self, query: str, trace: list) -> list:
        """
        Novelty-check mode: run hybrid_search against TKDL/pharmacopoeia/case_law first,
        then fall back to statute text if no prior-art match found.
        """
        all_chunks = []
        for cat in _NOVELTY_CATEGORIES:
            results = self.qe.hybrid_search(query, limit=3, category=cat)
            trace.append({
                "step": "retrieval",
                "category": cat,
                "chunks_found": len(results),
                "query": query,
            })
            all_chunks.extend(results)

        if not all_chunks:
            # Fallback: unrestricted hybrid search
            all_chunks = self.qe.hybrid_search(query, limit=5)
            trace.append({"step": "retrieval_fallback", "chunks_found": len(all_chunks)})

        return all_chunks

    def _precedent_lookup(self, query: str, trace: list) -> list:
        """
        Precedent-lookup mode: CasePrecedent graph traversal first, then vector.
        """
        # 1. Graph: find CasePrecedent nodes matching query keywords
        keywords = self._extract_keywords(query)
        graph_chunks = []
        for kw in keywords[:3]:
            hits = self.qe.neo4j.get_case_precedents_for_instrument(kw, limit=5)
            trace.append({"step": "graph_precedent", "keyword": kw, "hits": len(hits)})
            for h in hits:
                graph_chunks.append({
                    "text": f"Case Precedent: {h['name']}",
                    "doc_id": h.get("doc_id", ""),
                    "metadata": h,
                    "expansion": "graph:precedent",
                })

        # 2. Vector search against case_law category
        vec_results = self.qe.hybrid_search(query, limit=5, category="ip/case_law")
        trace.append({"step": "retrieval", "category": "ip/case_law", "chunks_found": len(vec_results)})

        return graph_chunks + vec_results

    def _jurisdiction_comparison(self, query: str, trace: list, language: str) -> dict:
        """
        Jurisdiction-comparison mode: parallel retrieval per jurisdiction.
        Returns a structured comparison dict with per-jurisdiction answers.

        Patch v1.1: first classifies supplement/food route vs drug/medicinal route
        for cross-border export queries before routing to sub-corpus.
        """
        # Detect which jurisdictions are mentioned; default to all if none explicit
        mentioned = [j for j in _JURISDICTIONS if j.lower() in query.lower()]
        if not mentioned:
            mentioned = ["India", "US", "EU"]

        # Patch v1.1: detect export route fork (supplement vs drug)
        route_hint = self._detect_export_route(query, trace)

        per_jurisdiction = {}
        all_chunks = []
        for jur in mentioned:
            # Get legal instruments for this jurisdiction from graph
            instruments = self.qe.neo4j.get_instruments_for_jurisdiction(jur, limit=5)
            trace.append({
                "step": "graph_jurisdiction",
                "jurisdiction": jur,
                "instruments_found": len(instruments),
                "route_hint": route_hint,
            })

            # Filter category based on route_hint
            category = None
            if route_hint == "export_compliance":
                category = "ip/export_compliance"

            jur_chunks = self.qe.hybrid_search(
                f"{query} {jur}", limit=3, category=category
            )
            trace.append({
                "step": "retrieval",
                "jurisdiction": jur,
                "category": category,
                "chunks_found": len(jur_chunks),
            })
            per_jurisdiction[jur] = jur_chunks
            all_chunks.extend(jur_chunks)

        # Synthesise a combined answer but also expose per-jurisdiction breakdown
        synthesis = self._synthesise(query, all_chunks, "jurisdiction_comparison",
                                     trace, language, jurisdiction_map=per_jurisdiction)
        synthesis["jurisdiction_map"] = {
            jur: [c.get("text", "")[:300] for c in chunks]
            for jur, chunks in per_jurisdiction.items()
        }
        return synthesis

    def _procedural(self, query: str, trace: list, language: str) -> dict:
        """
        Procedural mode (Patch v1.1): retrieve licensing/export chunks,
        order them by stage metadata, render as numbered sequence.
        """
        all_chunks = []
        for cat in _PROCEDURAL_CATEGORIES:
            results = self.qe.hybrid_search(query, limit=5, category=cat)
            trace.append({"step": "retrieval", "category": cat, "chunks_found": len(results)})
            all_chunks.extend(results)

        # Stage ordering via metadata — not LLM inference (preserves no-hallucination guarantee)
        def _stage_rank(chunk):
            stage = (chunk.get("metadata") or {}).get("stage", "") or chunk.get("stage", "")
            try:
                return _STAGE_ORDER.index(stage)
            except ValueError:
                return len(_STAGE_ORDER)  # unknown stages go last

        ordered = sorted(all_chunks, key=_stage_rank)
        trace.append({"step": "stage_ordering", "chunks_ordered": len(ordered)})

        # Build procedural answer string directly (no extra LLM call for ordering)
        procedural_notes = []
        for i, chunk in enumerate(ordered[:8], 1):
            meta = chunk.get("metadata") or {}
            stage = meta.get("stage") or chunk.get("stage", "")
            citation_src = chunk.get("metadata") or {}
            from src.utils.citation_formatter import format_citation
            cite = format_citation(citation_src)
            note_type = "Procedural note" if (
                cite == "Unknown Source" or "portal" in chunk.get("text", "").lower()
            ) else f"According to {cite}"
            procedural_notes.append(
                f"{i}. [{stage.upper() or 'STEP'}] {note_type}: {chunk.get('text', '')[:300]}"
            )

        answer = "\n".join(procedural_notes) if procedural_notes else self.qe._FALLBACK

        from src.utils.citation_formatter import format_source_object
        sources = [format_source_object(c) for c in ordered[:8]]

        return {
            "answer":   answer,
            "sources":  sources,
            "trace":    trace,
            "mode":     "procedural",
            "language": language,
            "tags":     ["[CLEAR]"],
        }

    # ------------------------------------------------------------------
    # Final synthesis (shared by novelty_check, precedent_lookup, jurisdiction_comparison)
    # ------------------------------------------------------------------

    def _synthesise(self, query: str, chunks: list, mode: str, trace: list,
                    language: str, session_context: list = None,
                    jurisdiction_map: dict = None) -> dict:
        """
        Run generate_answer() over the already-retrieved chunks.
        Guardrail (no hallucination) is enforced by query_engine.generate_answer.
        """
        from src.utils.citation_formatter import format_source_object
        import re as _re

        if not chunks:
            return {
                "answer":   self.qe._FALLBACK,
                "sources":  [],
                "trace":    trace,
                "mode":     mode,
                "language": language,
                "tags":     [],
            }

        # Override qdrant manager's results by directly building the context
        context_chunks = [c.get("text", "") for c in chunks if c.get("text")]
        context = "\n---\n".join(context_chunks[:6])  # cap at 6 chunks for context window

        system_msg = (
            "You are a read-only retrieval assistant for Ayurveda IP and regulatory law. "
            "Your ONLY job is to extract and quote relevant information from the CONTEXT block below. "
            "Do NOT use knowledge from your training data. "
            "For each factual claim, prefix with [CLEAR], [AMBIGUOUS], or [INFERRED] as appropriate. "
            "ELIGIBLE_FOR claims MUST always be [INFERRED]. "
            f"If CONTEXT does not answer the question, say exactly: \"{self.qe._FALLBACK}\""
        )

        # Include session context for continuity (Phase 8)
        messages = []
        if session_context:
            messages.extend(session_context[-4:])  # last 2 turns max
        messages += [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": f"CONTEXT:\n{context}\n\nQUESTION: {query}"},
        ]

        answer = self.qe._FALLBACK
        try:
            if self._synthesis_api_key:
                from openai import OpenAI
                client = OpenAI(api_key=self._synthesis_api_key, base_url=self._synthesis_base_url)
                resp = client.chat.completions.create(
                    model=self._synthesis_model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1024,
                )
                answer = resp.choices[0].message.content.strip()
            else:
                import ollama
                client = ollama.Client(host=self._ollama_host)
                resp = client.chat(
                    model=self._synthesis_model,
                    messages=messages,
                    options={"temperature": 0.0, "num_predict": 1024},
                )
                answer = resp["message"]["content"].strip()
        except Exception as e:
            logger.warning("Synthesis LLM failed (%s)", e)
            answer = f"LLM synthesis error: {e}"

        tags_found = list(set(_re.findall(r'\[(CLEAR|AMBIGUOUS|INFERRED)\]', answer)))
        sources = [format_source_object(c) for c in chunks[:6]]

        # Phase 9: post-generation guardrail — downgrade ungrounded [CLEAR] claims
        try:
            from src.utils.verifier import verify_and_downgrade
            answer = verify_and_downgrade(answer, chunks[:6])
            # Re-parse tags after possible downgrades
            tags_found = list(set(_re.findall(r'\[(CLEAR|AMBIGUOUS|INFERRED)\]', answer)))
        except Exception as e:
            logger.debug("Verifier skipped: %s", e)

        trace.append({"step": "synthesis", "chunks_used": len(chunks), "tags": tags_found})

        return {
            "answer":   answer,
            "sources":  sources,
            "trace":    trace,
            "mode":     mode,
            "language": language,
            "tags":     tags_found,
        }


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_language(self, text: str) -> str:
        """Detect query language for downstream rendering."""
        try:
            ep = self.qe.embedding_processor
            if ep and hasattr(ep, "detect_language"):
                return ep.detect_language(text)
        except Exception:
            pass
        return "en"

    def _extract_keywords(self, query: str) -> list:
        """Naive keyword extractor: words > 4 chars, not stopwords."""
        _STOP = {"what", "when", "where", "which", "does", "this", "that",
                 "with", "from", "have", "about", "under", "india"}
        words = re.findall(r'\b[A-Za-z]{5,}\b', query)
        return [w for w in words if w.lower() not in _STOP][:6]

    def _detect_export_route(self, query: str, trace: list) -> Optional[str]:
        """
        Patch v1.1: detect whether a cross-border export query is asking about
        the supplement/food route or drug/medicinal route.
        Returns 'export_compliance' (supplement route) or None (let orchestrator decide).
        """
        q = query.lower()
        if any(k in q for k in ("supplement", "dietary", "food", "dshea", "21 cfr")):
            route = "export_compliance"
        elif any(k in q for k in ("drug", "medicinal", "botanical drug", "anda", "thmpd")):
            route = "export_compliance"  # still export_compliance but drug sub-corpus
        else:
            route = None
        trace.append({"step": "route_detection", "route": route})
        return route
