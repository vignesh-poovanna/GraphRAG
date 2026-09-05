#!/usr/bin/env python3
"""
Extract concepts from already-imported chunks and write them into Neo4j.
Also auto-infers document categories (D1) and doc-doc relationships (D2/D3).

Run AFTER import_docs.py. Safe to stop and restart — the SQLite cache in
ConceptExtractor means unchanged chunks cost zero LLM calls on re-runs.

Usage:
    python scripts/extract_concepts.py
    python scripts/extract_concepts.py --batch-size 6
    python scripts/extract_concepts.py --dry-run        # extract + print, no DB writes
    python scripts/extract_concepts.py --check-ollama   # just verify Ollama is reachable
    python scripts/extract_concepts.py --doc-id <id>    # limit to one document
    python scripts/extract_concepts.py --skip-auto-link # skip relationship inference

Prerequisites:
    1. Ollama running locally:  ollama serve
    2. Model pulled:            ollama pull llama3.2:3b
    3. pip install ollama

Part D coverage:
  D1 — suggested_category piggybacked onto Ollama batch response; updates
       Neo4j doc nodes that have category='uncategorized'.
  D2 — auto_link_related_documents() runs concept-overlap + embedding-similarity
       linking after all extraction is complete.
  D3 — manual related: frontmatter edges already tagged via='manual' in import_docs.py.
       Inferred edges use via='shared_concepts' or via='embedding_similarity'.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.utils.neo4j_utils import Neo4jHelper
from src.processors.concept_extractor import ConceptExtractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(
        description="Extract concepts + auto-infer relationships from imported chunks"
    )
    p.add_argument("--model", default="llama3.2:3b", help="Ollama model name")
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--cache-path", default="concept_cache.db")
    p.add_argument("--batch-size", type=int, default=7, help="Chunks per Ollama call (6-8 recommended)")
    p.add_argument("--dry-run", action="store_true", help="Print extracted concepts without writing to Neo4j")
    p.add_argument("--check-ollama", action="store_true")
    p.add_argument("--doc-id", default=None, help="Limit to a single document ID")
    p.add_argument("--skip-auto-link", action="store_true", help="Skip doc-relationship auto-inference")
    p.add_argument("--min-shared-concepts", type=int, default=2)
    p.add_argument("--similarity-threshold", type=float, default=0.75)
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


# ------------------------------------------------------------------
# Neo4j helpers
# ------------------------------------------------------------------

def fetch_chunks(helper, doc_id=None):
    """Fetch Chunk nodes (created by import_docs.py via Neo4jManager)."""
    if doc_id:
        q = """
        MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
        RETURN c.id AS chunk_id, c.text AS text, d.id AS doc_id, d.category AS doc_category
        ORDER BY c.position
        """
        with helper.driver.session() as s:
            return [dict(r) for r in s.run(q, doc_id=doc_id)]
    q = """
    MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
    RETURN c.id AS chunk_id, c.text AS text, d.id AS doc_id, d.category AS doc_category
    """
    with helper.driver.session() as s:
        return [dict(r) for r in s.run(q)]


def fetch_all_doc_chunks_embeddings(helper):
    """
    Compute a mean embedding per document from Qdrant payload vectors.
    Returns {doc_id: np.array} or {} if Qdrant unreachable.
    Used by auto_link_related_documents for embedding-similarity (D2).
    """
    try:
        import numpy as np
        from src.config import Config
        from src.database.qdrant_manager import QdrantManager
        from src.processors.embedding_processor import EmbeddingProcessor

        config = Config()
        emb_proc = EmbeddingProcessor(config)
        emb_proc.load_model()
        qdrant = QdrantManager(config, emb_proc)
        qdrant.connect()

        # Scroll all points to get (doc_id, vector) pairs
        offset = None
        doc_vecs = {}  # doc_id -> list of vectors
        while True:
            result, offset = qdrant.client.scroll(
                collection_name=qdrant.collection_name,
                with_vectors=True,
                limit=500,
                offset=offset,
            )
            for pt in result:
                did = pt.payload.get("doc_id")
                if did and pt.vector:
                    doc_vecs.setdefault(did, []).append(pt.vector)
            if offset is None:
                break

        emb_proc.unload_model()
        qdrant.close()

        # Mean-pool per document
        return {did: np.mean(vecs, axis=0) for did, vecs in doc_vecs.items() if vecs}
    except Exception as exc:
        logger.warning("Could not build doc embeddings for similarity linking: %s", exc)
        return {}


def write_concepts(helper, chunk_id, extraction):
    """Write entities + MENTIONS + entity-entity edges for one chunk.
    Chunk nodes are keyed by chunk_id from the Chunk label (HAS_CHUNK schema).
    MENTIONS is written as (:Chunk)-[:MENTIONS]->(:Entity).
    """
    for ent in extraction.get("entities", []):
        name = ent.get("name", "").strip()
        if not name:
            continue
        helper.create_entity(name, entity_type=ent.get("type", ""))
        # Write MENTIONS edge from Chunk node directly
        with helper.driver.session() as s:
            s.run(
                """
                MATCH (c:Chunk {id: $chunk_id})
                MERGE (e:Entity {name: $entity_name})
                MERGE (c)-[:MENTIONS]->(e)
                """,
                chunk_id=chunk_id, entity_name=name,
            )

    for rel in extraction.get("relationships", []):
        src = rel.get("source", "").strip()
        tgt = rel.get("target", "").strip()
        if src and tgt:
            helper.link_entities(src, tgt, rel_type="RELATED_TO", weight=1.0)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    extractor = ConceptExtractor(
        model=args.model,
        host=args.ollama_host,
        cache_path=args.cache_path,
        batch_size=args.batch_size,
    )

    if args.check_ollama:
        ok = extractor.is_available()
        print("Ollama reachable: %s" % ok)
        sys.exit(0 if ok else 1)

    if not extractor.is_available():
        logger.error(
            "Ollama not reachable at %s. "
            "Start it with: ollama serve  then: ollama pull %s",
            args.ollama_host, args.model,
        )
        sys.exit(1)
    logger.info("Ollama OK — model: %s", args.model)

    config = Config()
    helper = Neo4jHelper(
        uri=config.get("neo4j.uri"),
        user=config.get("neo4j.user"),
        password=config.get("neo4j.password"),
    )

    try:
        msg = helper.verify_connection()
        if "failed" in msg.lower():
            logger.error("Neo4j: %s", msg)
            sys.exit(1)
        logger.info("Neo4j connected")

        chunks = fetch_chunks(helper, doc_id=args.doc_id)
        if not chunks:
            logger.warning("No Content nodes found — run import_docs.py first.")
            sys.exit(0)
        logger.info("Found %d chunks", len(chunks))

        total_entities = 0
        total_rels = 0
        # Track suggested categories per doc — use the most common suggestion
        # across all chunks for a given doc (majority vote avoids noise).
        doc_category_votes = {}  # doc_id -> {category: count}

        batch_size = args.batch_size
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            logger.info("Chunks %d-%d / %d", i + 1, min(i + batch_size, len(chunks)), len(chunks))
            results = extractor.extract_batch(batch)

            for chunk in batch:
                cid = chunk["chunk_id"]
                did = chunk["doc_id"]
                extraction = results.get(cid, {"entities": [], "relationships": [], "suggested_category": ""})

                ents = extraction.get("entities", [])
                rels = extraction.get("relationships", [])
                total_entities += len(ents)
                total_rels += len(rels)

                # D1 — collect category suggestions (only for uncategorized docs)
                if chunk.get("doc_category", "") in ("uncategorized", "", None):
                    cat = extraction.get("suggested_category", "").strip().lower()
                    if cat:
                        votes = doc_category_votes.setdefault(did, {})
                        votes[cat] = votes.get(cat, 0) + 1

                if args.dry_run:
                    print("chunk=%s  entities=%d  rels=%d  cat=%r" % (
                        cid[:8], len(ents), len(rels),
                        extraction.get("suggested_category", ""),
                    ))
                    for e in ents:
                        print("  [entity] %s (%s)" % (e.get("name"), e.get("type")))
                    for r in rels:
                        print("  [rel]    %s -> %s [%s]" % (r.get("source"), r.get("target"), r.get("relation")))
                else:
                    write_concepts(helper, cid, extraction)

        # D1 — apply winning category suggestion per doc
        if not args.dry_run:
            for did, votes in doc_category_votes.items():
                best = max(votes, key=votes.get)
                helper.update_document_category(did, best)
                logger.debug("Auto-categorized doc %s -> %s", did, best)
            if doc_category_votes:
                logger.info("Auto-categorized %d previously-uncategorized docs", len(doc_category_votes))

        # D2 — auto-link related documents (skip if --doc-id limits scope)
        if not args.skip_auto_link and not args.dry_run and not args.doc_id:
            logger.info("Building doc-level embeddings for similarity linking ...")
            doc_embeddings = fetch_all_doc_chunks_embeddings(helper)
            logger.info("Running auto_link_related_documents ...")
            linked = helper.auto_link_related_documents(
                min_shared_concepts=args.min_shared_concepts,
                threshold=args.similarity_threshold,
                doc_embeddings=doc_embeddings if doc_embeddings else None,
            )
            logger.info(
                "Auto-linked: shared_concepts=%d  embedding_similarity=%d",
                linked["shared_concepts"], linked["embedding_similarity"],
            )

        logger.info(
            "Done. entities=%d  relationships=%d  dry_run=%s",
            total_entities, total_rels, args.dry_run,
        )

    finally:
        helper.close()


if __name__ == "__main__":
    main()
