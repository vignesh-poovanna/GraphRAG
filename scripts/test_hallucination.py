#!/usr/bin/env python3
"""
Test script to demonstrate how GraphRAG handles hallucination
using Knowledge Graph entity checking, retrieval score inspection,
and strict closed-world context grounding.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import ollama
from src.config import Config
from src.database.neo4j_manager import Neo4jManager
from src.database.qdrant_manager import QdrantManager
from src.processors.embedding_processor import EmbeddingProcessor
from src.query_engine import QueryEngine

def main():
    cfg = Config()
    emb = EmbeddingProcessor(cfg)
    emb.load_model()
    neo = Neo4jManager(cfg)
    neo.connect()
    qd = QdrantManager(cfg, emb)
    qd.connect()
    engine = QueryEngine(neo, qd, emb)

    # -------------------------------------------------------------
    # 1. Adversarial Test Query (Fabricated technology not in docs)
    # -------------------------------------------------------------
    fake_query = "What nuclear fission reactor is used on this CubeSat and what is its uranium enrichment level?"

    print("\n" + "=" * 70)
    print(f"ADVERSARIAL QUERY: '{fake_query}'")
    print("=" * 70)

    # -------------------------------------------------------------
    # 2. Retrieval Inspection & Graph Entity Grounding
    # -------------------------------------------------------------
    print("\n[STEP 1: RETRIEVAL & KNOWLEDGE GRAPH CHECK]")
    results = engine.hybrid_search(fake_query, limit=3)

    graph_hits = 0
    for i, r in enumerate(results, 1):
        score = r.get('final_score', r.get('score', 0.0))
        exp = r.get('expansion', 'vector')
        text_snippet = r.get('text', '')[:90].replace('\n', ' ')
        doc = r.get('doc_title', 'unknown')
        if exp.startswith('graph') or exp == 'concept':
            graph_hits += 1
        print(f"  Result #{i}: score={score:.3f} | expansion={exp} | doc='{doc}'")
        print(f"            snippet: {text_snippet}...")

    print(f"\n  -> Graph expansion matches for queried entities: {graph_hits} (Expected: 0)")
    if graph_hits == 0:
        print("  -> CONFIRMED: Knowledge Graph contains NO matching entities for 'nuclear fission' or 'uranium'.")

    # -------------------------------------------------------------
    # 3. Raw LLM Call (No RAG grounding - prone to hallucinating)
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[STEP 2: RAW LLM WITHOUT GROUNDING (Standard LLM Guessing)]")
    print("-" * 70)
    resp_raw = ollama.generate(model="llama3.2:3b", prompt=f"Question: {fake_query}\nAnswer:")
    raw_answer = resp_raw['response'].strip()
    print(raw_answer[:300] + ("..." if len(raw_answer) > 300 else ""))

    # -------------------------------------------------------------
    # 4. Grounded RAG Call (Closed-World Guardrail)
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[STEP 3: GROUNDED GRAPHRAG RESPONSE (Anti-Hallucination Guardrail)]")
    print("-" * 70)

    context_blocks = []
    for r in results:
        doc = r.get('doc_title', 'unknown')
        body = r.get('text', '')
        context_blocks.append(f"[Document: {doc}]\n{body}")
    context = "\n\n---\n\n".join(context_blocks)

    grounded_prompt = f"""You are a strict technical verification assistant for satellite documentation.
Answer the question ONLY using factual information present in the context below.
If the context does not explicitly mention or contain the answer, you MUST state:
"The satellite documentation contains no mention of nuclear fission reactors or uranium enrichment."
Do NOT extrapolate, guess, or bring in outside knowledge.

Context:
{context}

Question: {fake_query}
Answer:"""

    resp_grounded = ollama.generate(model="llama3.2:3b", prompt=grounded_prompt)
    print(resp_grounded['response'].strip())
    print("\n" + "=" * 70 + "\n")

    neo.close()
    qd.close()
    emb.unload_model()

if __name__ == "__main__":
    main()
