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
            
            # Enhance results with document information
            enhanced_results = []
            for result in search_results:
                # Get document information from Neo4j
                doc_info = self.neo4j.get_document_by_id(result.get('doc_id'))
                if doc_info:
                    result['document'] = doc_info
                    
                # Get chunk context if needed
                chunk_context = self.neo4j.get_chunk_context(result['id'], context_size=1)
                if chunk_context:
                    result['context'] = {
                        'previous': [c.get('text', '') for c in chunk_context.get('previous', [])],
                        'next': [c.get('text', '') for c in chunk_context.get('next', [])]
                    }
                
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
            # Step 1: vector search (fetch 2x for reranking headroom)
            semantic_results = self.semantic_search(query, limit * 2, category)
            if not semantic_results:
                logger.warning("No semantic search results found")
                return []

            graph_weight = 1.0 - semantic_weight
            result_map = {}   # chunk_id -> result dict
            seen_doc_ids = set()

            for sem in semantic_results:
                doc_id = sem.get('doc_id')
                if not doc_id:
                    continue
                seen_doc_ids.add(doc_id)
                result_map[sem['id']] = {
                    'id': sem['id'],
                    'doc_id': doc_id,
                    'text': sem['text'],
                    'semantic_score': sem['score'],
                    'graph_score': 0.0,
                    'concept_score': 0.0,
                    'final_score': sem['score'] * semantic_weight,
                    'document': sem.get('document', {}),
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
                        # Use rel_weight from edge (D3); fall back to 0.5 for legacy edges
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
                    # Score proportional to entity overlap fraction (max overlap = 1.0)
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