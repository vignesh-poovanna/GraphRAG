"""
Query engine for hybrid Neo4j and Qdrant search
"""

import logging
from typing import List, Dict, Any, Optional, Union
import uuid

logger = logging.getLogger(__name__)

class QueryEngine:
    """Hybrid query engine for Neo4j and Qdrant databases"""
    
    def __init__(self, neo4j_manager, qdrant_manager, embedding_processor=None):
        """Initialize with database managers"""
        self.neo4j = neo4j_manager
        self.qdrant = qdrant_manager
        self.embedding_processor = embedding_processor
        
        # Verify connections
        self._verify_connections()
    
    def _verify_connections(self):
        """Verify database connections"""
        if not self.neo4j.driver:
            logger.warning("Neo4j connection not established, attempting to connect")
            self.neo4j.connect()
            
        if not self.qdrant.client:
            logger.warning("Qdrant connection not established, attempting to connect")
            self.qdrant.connect()
    
    def semantic_search(self, query: str, limit: int = 5, category: Optional[str] = None) -> List[Dict[Any, Any]]:
        """Perform semantic search using Qdrant"""
        logger.info(f"Semantic search: '{query}' (limit: {limit}, category: {category})")
        
        # Set up filter if category is provided
        filter_conditions = None
        if category:
            filter_conditions = {'category': category}
            
        # Perform vector search
        try:
            if not self.embedding_processor:
                logger.error("No embedding processor available for semantic search")
                return []
                
            # Use Qdrant for vector search
            search_results = self.qdrant.search(
                query_text=query,
                limit=limit,
                filter_conditions=filter_conditions
            )
            
            # Enhance results with document information efficiently
            enhanced_results = []
            doc_cache = {}
            for result in search_results:
                d_id = result.get('doc_id')
                if d_id:
                    if d_id not in doc_cache:
                        doc_cache[d_id] = self.neo4j.get_document_by_id(d_id)
                    result['document'] = doc_cache[d_id]
                
                enhanced_results.append(result)
            
            return enhanced_results
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []
    
    def category_search(self, category: str, limit: int = 10) -> List[Dict[Any, Any]]:
        """Search for documents by category using Neo4j"""
        logger.info(f"Category search: '{category}' (limit: {limit})")
        
        try:
            # Use Neo4j for category search
            results = self.neo4j.search_by_category(category, limit)
            return results
        except Exception as e:
            logger.error(f"Error in category search: {str(e)}")
            return []
    
    def get_document_with_chunks(self, doc_id: str) -> Dict[Any, Any]:
        """Get document with all its chunks"""
        logger.info(f"Getting document with chunks: {doc_id}")
        
        try:
            # Get document from Neo4j
            document = self.neo4j.get_document_by_id(doc_id)
            if not document:
                logger.warning(f"Document not found: {doc_id}")
                return {}
            
            # Get chunks from Neo4j
            chunks = self.neo4j.get_document_chunks(doc_id)
            document['chunks'] = chunks
            
            return document
        except Exception as e:
            logger.error(f"Error getting document with chunks: {str(e)}")
            return {}
    
    def hybrid_search(self, query: str, limit: int = 5, category: Optional[str] = None,
                       semantic_weight: float = 0.7) -> List[Dict[Any, Any]]:
        """
        Hybrid search: vector similarity + graph expansion + concept graph expansion.

        Score composition:
          semantic hit:        score * semantic_weight
          graph-adjacent doc:  rel_weight * (1 - semantic_weight)   [via-ordered]
          concept-expanded:    overlap_fraction * 0.3 * (1 - semantic_weight)
        """
        logger.info(f"Hybrid search: '{query}' (limit: {limit}, category: {category})")

        try:
            import re
            # Step 1: vector search with wider candidate pool for reranking headroom
            candidate_limit = max(limit * 8, 40)
            semantic_results = self.semantic_search(query, candidate_limit, category)
            if not semantic_results:
                logger.warning("No semantic search results found")
                return []

            # Extract query tokens, statute names, and section numbers for reranking
            q_lower = query.lower()
            sections = re.findall(r'\b(?:section|sec\.?|article|rule)\s*(\d+[a-z]?(?:\([a-z0-9]+\))?)', q_lower)
            statute_keywords = [
                "biological diversity", "nagoya protocol", "patents act", "patent",
                "trade mark", "trademark", "geographical indication", "copyright",
                "pharmacopoeia", "jan vishwas", "tribunal", "ayush"
            ]
            matched_statutes = [sk for sk in statute_keywords if sk in q_lower]
            q_words = set(w for w in re.findall(r'\b[a-z]{3,}\b', q_lower) if w not in {
                "what", "where", "when", "which", "does", "have", "with", "from", "under", "this", "that"
            })

            graph_weight = 1.0 - semantic_weight
            result_map = {}   # chunk_id -> result dict
            seen_doc_ids = set()

            for sem in semantic_results:
                doc_id = sem.get('doc_id')
                if not doc_id:
                    continue
                seen_doc_ids.add(doc_id)

                text_lower = sem.get('text', '').lower()
                doc_dict = sem.get('document') or {}
                title_lower = (doc_dict.get('title') or sem.get('title') or '').lower()
                act_lower = (doc_dict.get('act_or_source_name') or sem.get('act_or_source_name') or '').lower()

                # Calculate lexical & statutory relevance boost
                boost = 0.0
                for sk in matched_statutes:
                    if sk in title_lower or sk in act_lower:
                        boost += 0.25
                        break

                for sec in sections:
                    patterns = [
                        rf'\bsection\s+{re.escape(sec)}\b',
                        rf'\b{re.escape(sec)}\.\s*\(',
                        rf'\barticle\s+{re.escape(sec)}\b',
                    ]
                    if any(re.search(p, text_lower) for p in patterns):
                        boost += 0.20
                        break

                text_words = set(re.findall(r'\b[a-z]{3,}\b', text_lower))
                if q_words:
                    overlap = len(q_words & text_words) / len(q_words)
                    boost += overlap * 0.15

                # Novelty-query boost: when query asks if something IS patentable,
                # promote chunks about Section 3 exclusions over rights/licensing chunks.
                _is_novelty_q = any(p in q_lower for p in (
                    "can i patent", "patentable", "prior art", "novelty",
                    "is it patentable", "qualify for patent", "eligible for patent",
                    "can be patented", "cannot be patented",
                ))
                if _is_novelty_q:
                    _excl_signals = (
                        "non-patentable", "no patent shall be granted",
                        "traditional knowledge", "section 3", "ayurvedic",
                        "prior art", "tkdl", "not patentable",
                    )
                    if any(sig in text_lower for sig in _excl_signals):
                        boost += 0.30

                final_sem_score = sem['score'] * semantic_weight + boost

                result_map[sem['id']] = {
                    'id': sem['id'],
                    'doc_id': doc_id,
                    'text': sem['text'],
                    'semantic_score': sem['score'],
                    'graph_score': 0.0,
                    'concept_score': 0.0,
                    'final_score': final_sem_score,
                    'document': doc_dict,
                    'context': sem.get('context', {}),
                    'expansion': 'vector',
                }

                # Step 2: graph-adjacent docs (RELATED_TO, via-ordered)
                related_docs = self.neo4j.get_related_documents(doc_id, limit=3)
                for rel_doc in related_docs:
                    rel_doc_id = rel_doc.get('id')
                    if not rel_doc_id or rel_doc_id in seen_doc_ids:
                        continue
                    rel_chunks = self.neo4j.get_document_chunks(rel_doc_id)
                    if not rel_chunks:
                        continue
                    rc = rel_chunks[0]
                    rc_id = rc.get('id')
                    if rc_id and rc_id not in result_map:
                        edge_w = float(rel_doc.get('rel_weight') or 0.5)
                        graph_score = edge_w * graph_weight
                        result_map[rc_id] = {
                            'id': rc_id,
                            'doc_id': rel_doc_id,
                            'text': rc.get('text', ''),
                            'semantic_score': 0.0,
                            'graph_score': graph_score,
                            'concept_score': 0.0,
                            'final_score': graph_score,
                            'document': rel_doc,
                            'context': {},
                            'expansion': 'graph:' + (rel_doc.get('via') or 'unknown'),
                        }

            # Step 3: concept-graph expansion (B3)
            top_chunk_ids = [r['id'] for r in semantic_results[:limit]]
            concept_hits = self.expand_via_concepts(
                top_chunk_ids,
                exclude_doc_ids=seen_doc_ids,
                limit=limit,
            )
            for hit in concept_hits:
                cid = hit.get('chunk_id')
                if cid and cid not in result_map:
                    overlap = float(hit.get('overlap', 1))
                    concept_score = (overlap / max(overlap, 5)) * 0.3 * graph_weight
                    result_map[cid] = {
                        'id': cid,
                        'doc_id': hit['doc_id'],
                        'text': hit.get('chunk_text', ''),
                        'semantic_score': 0.0,
                        'graph_score': 0.0,
                        'concept_score': concept_score,
                        'final_score': concept_score,
                        'document': {'id': hit['doc_id'], 'title': hit.get('doc_title', ''),
                                     'category': hit.get('doc_category', '')},
                        'context': {},
                        'expansion': 'concept',
                    }

            # Step 4: sort and return
            results = sorted(result_map.values(), key=lambda x: x['final_score'], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            return []
    
    def expand_via_concepts(self, chunk_ids, exclude_doc_ids=None, limit=10):
        """
        Part B3 — concept graph expansion.

        Given a list of chunk IDs (top vector-search hits):
          1. Find Entity nodes those chunks MENTION.
          2. Find other documents that also mention those entities.
          3. Return them as candidate results (caller assigns lower weight).

        Falls back gracefully to [] if no Entity nodes exist yet
        (i.e., extract_concepts.py hasn't been run yet).
        """
        try:
            entities = self.neo4j.get_entities_for_chunks(chunk_ids)
            if not entities:
                return []  # concept graph not populated yet — silent no-op

            entity_names = [e['name'] for e in entities]
            logger.debug("Concept expansion: %d entities from top chunks", len(entity_names))

            return self.neo4j.get_documents_for_entities(
                entity_names,
                exclude_doc_ids=exclude_doc_ids,
                limit=limit,
            )
        except Exception as e:
            logger.warning(f"Concept expansion failed (non-fatal): {str(e)}")
            return []

    def expand_context(self, chunk_id: str, context_size: int = 2) -> Dict[Any, Any]:
        """Expand context around a specific chunk"""
        logger.info(f"Expanding context for chunk: {chunk_id} (size: {context_size})")
        
        try:
            # Get chunk context from Neo4j
            context = self.neo4j.get_chunk_context(chunk_id, context_size)
            if not context:
                logger.warning(f"No context found for chunk: {chunk_id}")
                return {}
            
            # Get document info
            doc_id = None
            if context.get('center'):
                chunk = context['center']
                doc_id = self.neo4j.get_document_by_chunk_id(chunk_id)
                if doc_id:
                    doc_info = self.neo4j.get_document_by_id(doc_id)
                    if doc_info:
                        context['document'] = doc_info
            
            return context
        except Exception as e:
            logger.error(f"Error expanding context: {str(e)}")
            return {}
    
    def suggest_related(self, doc_id: str, limit: int = 5) -> List[Dict[Any, Any]]:
        """Suggest related documents based on category and graph connections"""
        logger.info(f"Suggesting related documents for: {doc_id} (limit: {limit})")
        
        try:
            # Get related documents from Neo4j
            related = self.neo4j.get_related_documents(doc_id, limit)
            return related
        except Exception as e:
            logger.error(f"Error suggesting related documents: {str(e)}")
            return []
    
    def get_all_categories(self) -> List[str]:
        """Get all available document categories"""
        logger.info("Getting all document categories")
        
        try:
            return self.neo4j.get_all_categories()
        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict[Any, Any]:
        """Get statistics from both databases"""
        logger.info("Getting database statistics")
        
        try:
            neo4j_stats = self.neo4j.get_statistics()
            qdrant_stats = self.qdrant.get_statistics()
            
            return {
                'neo4j': neo4j_stats,
                'qdrant': qdrant_stats
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {}

    _FALLBACK = "The documentation does not contain information regarding this question."

    def generate_answer(
        self,
        query: str,
        limit: int = 6,
        model: str = None,
        temperature: float = 0.0,
        host: str = None,
        language: str = "en",
        session_context: list = None,   # [{role, content}, ...] last 3 turns
    ) -> dict:
        """
        Perform hybrid retrieval and generate a strictly grounded answer.

        Phase 4: every source chunk is rendered through citation_formatter.
        Phase 6: LLM is instructed to tag claims as [CLEAR], [AMBIGUOUS], or [INFERRED].
        Phase 7: uses SYNTHESIS_LLM from config; falls back to local Ollama.

        Returns:
            {
              "answer":   str,
              "sources":  list of format_source_object() dicts,
              "context":  str,
              "language": str,
              "tags":     list of tag strings found in the answer
            }
        """
        from src.utils.citation_formatter import format_source_object

        results = self.hybrid_search(query, limit=limit)
        if not results:
            return {"answer": self._FALLBACK, "sources": [], "context": "", "language": language, "tags": []}

        # Number chunks so LLM can cite inline; also build source objects for frontend
        context_chunks = [r.get("text", "") for r in results if r.get("text")]
        numbered_context = "\n---\n".join(
            f"[{i+1}] {t}" for i, t in enumerate(context_chunks)
        )
        context = numbered_context  # kept for the return value
        sources = [format_source_object(r) for r in results]

        # Phase 7: resolve synthesis model
        if model is None:
            model = (
                self.neo4j.config.get("llm.synthesis_model", "qwen/qwen3.8-27b")
                if hasattr(self.neo4j, "config") else "qwen/qwen3.8-27b"
            )
        if host is None:
            host = (
                self.neo4j.config.get("llm.ollama_host", "http://localhost:11434")
                if hasattr(self.neo4j, "config") else "http://localhost:11434"
            )

        lang_instruction = (
            "Respond in Hindi (Devanagari script). "
            if language == "hi" else
            "Respond in the same language as the question. "
            if language not in ("en", "") else ""
        )

        system_msg = (
            f"{lang_instruction}"
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
            f"- If the CONTEXT has zero relevant content, respond with EXACTLY: \"{self._FALLBACK}\""
        )

        # Build messages: history (if any) + system + user
        user_msg = f"CONTEXT:\n{numbered_context}\n\nQUESTION: {query}"
        messages = []
        if session_context:
            messages.extend(session_context[-3:])  # cap at 3 turns
        messages += [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ]

        try:
            api_key = self.neo4j.config.get("llm.synthesis_api_key", "") if hasattr(self.neo4j, "config") else ""
            base_url = self.neo4j.config.get("llm.synthesis_base_url", "") if hasattr(self.neo4j, "config") else ""

            if api_key:
                # Use OpenAI-compatible client (Groq, Cerebras, etc.)
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=base_url)
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=600,
                )
                answer = resp.choices[0].message.content.strip()
            else:
                # Fallback: local Ollama
                import ollama
                client = ollama.Client(host=host)
                response = client.chat(
                    model=model,
                    messages=messages,
                    options={"temperature": temperature, "num_predict": 768},
                )
                answer = response["message"]["content"].strip()
        except Exception as exc:
            logger.warning(f"Ollama generation failed: {exc}")
            answer = f"Error generating answer via LLM: {exc}"

        # If answer is fallback, don't return unrelated sources
        if self._FALLBACK in answer or answer.strip() == self._FALLBACK:
            sources = []

        # Phase 6: parse tags from answer and annotate sources
        import re as _re
        tags_found = _re.findall(r'\[(CLEAR|AMBIGUOUS|INFERRED)\]', answer)

        return {
            "answer":   answer,
            "sources":  sources,
            "context":  context,
            "language": language,
            "tags":     list(set(tags_found)),
        }