#!/usr/bin/env python3
"""End-to-end verification script for GraphRAG."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.utils.neo4j_utils import Neo4jHelper
from src.query_engine import QueryEngine
from src.database.neo4j_manager import Neo4jManager
from src.database.qdrant_manager import QdrantManager
from src.processors.embedding_processor import EmbeddingProcessor

def main():
    cfg = Config()
    helper = Neo4jHelper(cfg.get('neo4j.uri'), cfg.get('neo4j.user'), cfg.get('neo4j.password'))
    
    print("\n--- 1. Auto-Link Related Documents (Part D2) ---")
    res = helper.auto_link_related_documents(min_shared_concepts=1, threshold=0.75)
    print(f"Auto-link result: {res}")
    
    with helper.driver.session() as s:
        links = s.run("""
            MATCH (d1:Document)-[r:RELATED_TO]->(d2:Document)
            WHERE r.via = 'shared_concepts'
            RETURN d1.title AS doc1, r.weight AS shared_concepts, d2.title AS doc2
        """).data()
        print(f"\nAuto-discovered Shared-Concept Links ({len(links)}):")
        for l in links:
            print(f"  * '{l['doc1']}' <---> '{l['doc2']}' (shared concepts: {l['shared_concepts']})")

        ents = s.run("MATCH (e:Entity) RETURN count(e) AS count").single()['count']
        rels = s.run("MATCH (:Entity)-[r:RELATED_TO]->(:Entity) RETURN count(r) AS count").single()['count']
        mentions = s.run("MATCH ()-[r:MENTIONS]->() RETURN count(r) AS count").single()['count']
        print(f"\nKnowledge Graph Stats:")
        print(f"  * Entities: {ents}")
        print(f"  * Entity Relationships: {rels}")
        print(f"  * Chunk MENTIONS Edges: {mentions}")

    helper.close()

    print("\n--- 2. End-to-End Query Verification (Hybrid + Concept Expansion) ---")
    emb = EmbeddingProcessor(cfg)
    emb.load_model()
    neo = Neo4jManager(cfg)
    neo.connect()
    qd = QdrantManager(cfg, emb)
    qd.connect()
    
    engine = QueryEngine(neo, qd, emb)
    
    queries = [
        "attitude control reaction wheels and heat",
        "power generation solar panels and battery",
        "thermal control and safe mode"
    ]
    
    for q in queries:
        print(f"\n>>> QUERY: '{q}'")
        results = engine.hybrid_search(q, limit=3)
        for i, r in enumerate(results, 1):
            src = r.get('source_type', 'unknown')
            exp = r.get('expansion', 'vector')
            score = r.get('final_score', r.get('score', 0.0))
            preview = r.get('text', '')[:100].replace('\n', ' ')
            print(f"  [{i}] doc='{r.get('doc_title')}' (score={score:.3f}, source={src}, expansion={exp})")
            print(f"      snippet: {preview}...")

    neo.close()
    qd.close()
    emb.unload_model()
    print("\n--- END-TO-END RUN COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    main()
