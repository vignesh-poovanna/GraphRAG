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
_NOVELTY_CATEGORIES = [
    "Ayurveda & Traditional Knowledge",
    "Patent Law & Examination",
    "Biodiversity & Access-Benefit Sharing",
]
_PROCEDURAL_CATEGORIES = [
    "Patent Law & Examination",
    "Trademarks & Geographical Indications",
    "Biodiversity & Access-Benefit Sharing",
    "Copyrights & Digital Media",
]

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
            # Extract follow-ups the same way _synthesise does (QE may or may not emit them)
            result.setdefault("follow_ups", [])
            fu_match = re.search(r'FOLLOW_UPS:\s*(\[.*?\])', result.get("answer", ""), re.DOTALL)
            if fu_match:
                try:
                    import json as _json
                    fus = _json.loads(fu_match.group(1))
                    result["follow_ups"] = [str(q).strip() for q in fus[:3]] if isinstance(fus, list) else []
                    result["answer"] = result["answer"][:fu_match.start()].rstrip()
                except Exception:
                    pass
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
- novelty_check: asks whether a formulation/ingredient/product is novel, patentable, or has prior art in any country
- jurisdiction_comparison: explicitly compares two or more named countries/legal systems side-by-side (e.g. "India vs US", "India and EU")
- precedent_lookup: asks about a specific NAMED court CASE or tribunal RULING (e.g. "Novartis v Union of India", "neem patent case")
- procedural: asks HOW TO do something — obtain a license, register, apply, file, or follow a step-by-step regulatory process
- general: any other question including what a statute/section SAYS or MEANS, definitions, compliance requirements, impact of a treaty/protocol

IMPORTANT: Questions asking what a section or provision says ("What does Section 3(p) say?") → general.
IMPORTANT: Questions about a treaty's or protocol's effect/impact → general.
IMPORTANT: jurisdiction_comparison ONLY when two or more specific countries are named for comparison.

Query: {query}

Reply with ONLY the category name, nothing else."""

        mode = "general"
        try:
            from openai import OpenAI
            client = None
            model = None

            if self._synthesis_api_key:
                client = OpenAI(api_key=self._synthesis_api_key, base_url=self._synthesis_base_url)
                model = self._synthesis_model
            elif self._classify_api_key:
                client = OpenAI(api_key=self._classify_api_key, base_url=self._classify_base_url)
                model = self._classify_model

            if client and model:
                resp = client.chat.completions.create(
                    model=model,
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

        trace.append({"step": "classify_llm", "mode": mode, "backend": "groq" if self._synthesis_api_key else ("cerebras" if self._classify_api_key else "ollama")})
        return mode

    # ------------------------------------------------------------------
    # Mode handlers
    # ------------------------------------------------------------------

    def _novelty_check(self, query: str, trace: list) -> list:
        """
        Novelty-check mode: run hybrid_search for prior-art and statutory criteria.
        """
        all_chunks = self.qe.hybrid_search(query, limit=10)
        trace.append({"step": "retrieval", "chunks_found": len(all_chunks)})
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
        Jurisdiction-comparison mode.

        Patch v1.2: only do per-jurisdiction parallel retrieval when the query
        EXPLICITLY names two or more jurisdictions for comparison (e.g. "India vs US").
        If fewer than 2 jurisdictions are explicitly named, treat it as a general
        retrieval so we don't poison the search query with "India", "US", "EU" suffixes.
        """
        mentioned = [j for j in _JURISDICTIONS if j.lower() in query.lower()]

        # ---- Single-jurisdiction (or no jurisdiction) query ----------------
        # e.g. "How does the Nagoya Protocol affect Ayurvedic exports?"
        # Appending country names would hurt retrieval; just do a clean hybrid search.
        if len(mentioned) < 2:
            trace.append({"step": "jurisdiction_single_pass",
                          "reason": "fewer than 2 jurisdictions mentioned; using clean hybrid search"})
            all_chunks = self.qe.hybrid_search(query, limit=10)
            trace.append({"step": "retrieval", "chunks_found": len(all_chunks)})
            return self._synthesise(query, all_chunks, "jurisdiction_comparison", trace, language)

        # ---- True multi-jurisdiction comparison ----------------------------
        route_hint = self._detect_export_route(query, trace)
        per_jurisdiction = {}
        all_chunks = []
        for jur in mentioned:
            instruments = self.qe.neo4j.get_instruments_for_jurisdiction(jur, limit=5)
            trace.append({
                "step": "graph_jurisdiction",
                "jurisdiction": jur,
                "instruments_found": len(instruments),
                "route_hint": route_hint,
            })
            category = "ip/export_compliance" if route_hint == "export_compliance" else None
            jur_chunks = self.qe.hybrid_search(
                f"{query} {jur}", limit=4, category=category
            )
            trace.append({
                "step": "retrieval",
                "jurisdiction": jur,
                "category": category,
                "chunks_found": len(jur_chunks),
            })
            per_jurisdiction[jur] = jur_chunks
            all_chunks.extend(jur_chunks)

        synthesis = self._synthesise(query, all_chunks, "jurisdiction_comparison",
                                     trace, language, jurisdiction_map=per_jurisdiction)
        synthesis["jurisdiction_map"] = {
            jur: [c.get("text", "")[:300] for c in chunks]
            for jur, chunks in per_jurisdiction.items()
        }
        return synthesis

    def _procedural(self, query: str, trace: list, language: str) -> dict:
        """
        Procedural mode: retrieve licensing/export/regulatory chunks and synthesise.
        """
        all_chunks = self.qe.hybrid_search(query, limit=10)
        trace.append({"step": "retrieval", "chunks_found": len(all_chunks)})
        return self._synthesise(query, all_chunks, "procedural", trace, language)

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

        # Number chunks so the LLM can cite them inline
        used_chunks = [c for c in chunks if c.get("text")][:8]
        numbered_context = "\n---\n".join(
            f"[{i+1}] {c['text']}" for i, c in enumerate(used_chunks)
        )

        system_msg = (
            "You are a concise regulatory assistant for Ayurveda IP, Indian patent law, and traditional knowledge. "
            "Answer the QUESTION using ONLY the numbered CONTEXT blocks below. "
            "Rules:\n"
            "- Write 3 to 6 short bullet points. Each bullet must be 1-2 sentences max.\n"
            "- Summarize the source in your own words — do NOT copy-paste entire sentences from the source.\n"
            "- After each bullet, cite the source number(s) in square brackets, e.g. [1] or [1][3].\n"
            "- Tag each bullet with ONE confidence marker: [CLEAR] if directly stated, [INFERRED] if derived, [AMBIGUOUS] if conflicting.\n"
            "- End your answer with a blank line then: **Sources:** followed by the cited numbers and their short titles.\n"
            "- After Sources, add a blank line then: **Verdict:** followed by a direct answer (e.g. Yes / No / Conditional) and one sentence explaining the key condition or reason.\n"
            "- After Verdict, add a blank line then: FOLLOW_UPS: [\"question 1?\", \"question 2?\", \"question 3?\"] — exactly 3 short follow-up questions the user might naturally ask next, as a JSON array on one line.\n"
            "- Do NOT add analysis beyond what is grounded in the context.\n"
            f"- If the CONTEXT has zero relevant content, respond with EXACTLY: \"{self.qe._FALLBACK}\""
        )

        # Include session context for continuity (Phase 8)
        messages = []
        if session_context:
            messages.extend(session_context[-4:])  # last 2 turns max
        messages += [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": f"CONTEXT:\n{numbered_context}\n\nQUESTION: {query}"},
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
                    max_tokens=600,
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

        # If answer is fallback, don't return unrelated sources
        if self.qe._FALLBACK in answer or answer.strip() == self.qe._FALLBACK:
            sources = []
        else:
            sources = [format_source_object(c) for c in chunks[:6]]

        tags_found = list(set(_re.findall(r'\[(CLEAR|AMBIGUOUS|INFERRED)\]', answer)))

        # Phase 9: post-generation guardrail — downgrade ungrounded [CLEAR] claims
        try:
            from src.utils.verifier import verify_and_downgrade
            answer = verify_and_downgrade(answer, chunks[:6])
            # Re-parse tags after possible downgrades
            tags_found = list(set(_re.findall(r'\[(CLEAR|AMBIGUOUS|INFERRED)\]', answer)))
        except Exception as e:
            logger.debug("Verifier skipped: %s", e)

        # Extract follow-up questions emitted inline by the LLM
        follow_ups = []
        fu_match = _re.search(r'FOLLOW_UPS:\s*(\[.*?\])', answer, _re.DOTALL)
        if fu_match:
            try:
                import json as _json
                follow_ups = _json.loads(fu_match.group(1))
                if not isinstance(follow_ups, list):
                    follow_ups = []
                follow_ups = [str(q).strip() for q in follow_ups[:3]]
            except Exception:
                follow_ups = []
            # Strip the FOLLOW_UPS line from the visible answer
            answer = answer[:fu_match.start()].rstrip()

        trace.append({"step": "synthesis", "chunks_used": len(chunks), "tags": tags_found})

        return {
            "answer":     answer,
            "sources":    sources,
            "trace":      trace,
            "mode":       mode,
            "language":   language,
            "tags":       tags_found,
            "follow_ups": follow_ups,
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
