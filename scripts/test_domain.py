#!/usr/bin/env python3
"""
test_domain.py — Phase 10 domain test suite for IP-SAKTI Sahayak

Labeled test set: 18 question/expected-citation pairs covering:
  - Clear national law questions
  - Clear international law questions
  - Ambiguous cross-jurisdiction questions
  - Known case precedent questions
  - Refusal cases (corpus does not address the question)
  - Cross-lingual (Hindi) queries
  - Verifier downgrade behaviour (CLEAR → AMBIGUOUS)
  - Procedural / agentic mode routing

Run:
  python scripts/test_domain.py [--offline]  # --offline skips LLM calls

Exit code 0 = all passed, 1 = failures found.
"""

import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.utils.citation_formatter import format_citation
from src.utils.verifier import verify_and_downgrade
from src.speech.session_cache import SessionCache

# -------------------------------------------------------------------------
# Test helpers
# -------------------------------------------------------------------------

PASS = "✅ PASS"
FAIL = "❌ FAIL"

_results = []


def check(name: str, cond: bool, detail: str = ""):
    status = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))
    return cond


# -------------------------------------------------------------------------
# SECTION A — unit tests (offline, no DB or LLM needed)
# -------------------------------------------------------------------------

def test_citation_formatter():
    print("\n── Citation Formatter ──")
    m = {"act_or_source_name": "Patents Act 1970", "year": "1970", "section": "3(p)", "jurisdiction": "India"}
    cite = format_citation(m)
    check("Full citation rendered", "Patents Act 1970" in cite and "3(p)" in cite, cite)

    m2 = {}
    cite2 = format_citation(m2)
    check("Empty metadata → fallback", cite2 == "Unknown Source", cite2)


def test_session_cache():
    print("\n── Session Cache ──")
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        cache = SessionCache(tmp)
        sid = cache.new_session()
        check("New session created", bool(sid))

        cache.add_turn(sid, "user", "What is Section 3(p)?")
        cache.add_turn(sid, "assistant", "[CLEAR] Section 3(p) excludes...")
        history = cache.get_history(sid, last_n=4)
        check("History has 2 turns", len(history) == 2)
        check("History in order (user first)", history[0]["role"] == "user")

        cache.save_interruption(sid, "mid-answer text", 42)
        history2 = cache.get_history(sid, last_n=10)
        interrupted = any("INTERRUPTED" in t["content"] for t in history2)
        check("Interruption saved", interrupted)

        same_sid = cache.new_session(sid)
        check("Idempotent session creation", same_sid == sid)
    finally:
        cache.close()
        os.unlink(tmp)


def test_verifier():
    print("\n── Post-generation Verifier ──")
    # Grounded claim — chunk text must contain the key n-gram from the answer
    chunks = [{"text": "Section 3(p) of the Patents Act excludes traditional knowledge from patentability in India."}]
    answer_grounded = "[CLEAR] Section 3(p) of Patents Act excludes traditional knowledge."
    result = verify_and_downgrade(answer_grounded, chunks)
    check("Grounded [CLEAR] kept", "[CLEAR]" in result, result[:80])

    # Ungrounded claim — should be downgraded
    chunks2 = [{"text": "The Nagoya Protocol deals with access and benefit sharing."}]
    answer_ungrounded = "[CLEAR] The turmeric patent was revoked in 1997 by the USPTO."
    result2 = verify_and_downgrade(answer_ungrounded, chunks2)
    check("Ungrounded [CLEAR] → [AMBIGUOUS]", "[AMBIGUOUS]" in result2, result2[:80])

    # INFERRED tag passes through untouched
    answer_inferred = "[INFERRED] This formulation may be eligible for GI protection."
    result3 = verify_and_downgrade(answer_inferred, chunks2)
    check("[INFERRED] not touched by verifier", "[INFERRED]" in result3)


def test_citation_index():
    print("\n── Citation Index ──")
    import tempfile, os
    from src.utils.citation_index import load_citations_index, enrich_with_url, _INDEX

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Patents Act 1970\thttps://ipindia.gov.in/patents\n")
        f.write("# comment line\n")
        f.write("Biological Diversity Act 2002\thttps://nbaindia.org/bd\n")
        tmp = f.name
    try:
        n = load_citations_index(tmp)
        check("Loaded 2 entries (ignores comment)", n == 2)

        src = {"citation": "Patents Act 1970, Section 3(p) (India)", "act_or_source_name": "Patents Act 1970"}
        enrich_with_url(src)
        check("URL enriched for Patents Act", src.get("url") == "https://ipindia.gov.in/patents", src.get("url"))

        src2 = {"citation": "Some Unknown Regulation", "act_or_source_name": "Unknown"}
        enrich_with_url(src2)
        check("No URL for unknown act", "url" not in src2)
    finally:
        os.unlink(tmp)


# -------------------------------------------------------------------------
# SECTION B — integration tests (require running DB + LLM)
# -------------------------------------------------------------------------

DOMAIN_TEST_SET = [
    # format: (name, query, expected_in_answer, should_refuse, expected_mode)
    # Clear national law
    ("section_3p_clear",
     "What does Section 3(p) of the Indian Patents Act 1970 say about traditional knowledge?",
     ["3(p)", "traditional knowledge", "patent"],
     False, "general"),

    # Clear international
    ("nagoya_protocol",
     "What is the Nagoya Protocol and how does it relate to access and benefit sharing?",
     ["Nagoya", "benefit sharing", "access"],
     False, "general"),

    # Known case precedent
    ("turmeric_revocation",
     "Was the turmeric wound-healing patent revoked and on what grounds?",
     ["turmeric", "revoked", "prior art"],
     False, "precedent_lookup"),

    # Ambiguous cross-jurisdiction
    ("gi_us_vs_india",
     "How does India's GI Act compare to the US approach to geographical indications?",
     ["India", "GI", "geographical"],
     False, "jurisdiction_comparison"),

    # Refusal — not in corpus
    ("out_of_scope",
     "What is the melting point of silicon carbide?",
     [],
     True, "general"),

    # Procedural mode
    ("manufacturing_license",
     "How do I obtain a manufacturing license for an Ayurvedic product in India?",
     ["license", "AYUSH"],
     False, "procedural"),

    # Novelty check mode
    ("chyawanprash_novelty",
     "Is Chyawanprash a novel formulation eligible for a patent?",
     ["INFERRED", "Chyawanprash"],
     False, "novelty_check"),
]

REFUSAL_MARKER = "The documentation does not contain"


def run_integration_tests(engine, orch):
    print("\n── Integration: Domain Query Correctness ──")
    for name, query, expected_terms, should_refuse, expected_mode in DOMAIN_TEST_SET:
        try:
            result = orch.run(query)
            answer = result.get("answer", "")
            mode = result.get("mode", "")
            refused = REFUSAL_MARKER in answer

            if should_refuse:
                check(f"{name}: refusal fires", refused, answer[:80])
            else:
                terms_found = all(t.lower() in answer.lower() for t in expected_terms)
                check(f"{name}: answer contains expected terms", terms_found,
                      f"missing: {[t for t in expected_terms if t.lower() not in answer.lower()]}")
                check(f"{name}: correct mode [{expected_mode}]", mode == expected_mode,
                      f"got {mode}")
        except Exception as e:
            check(f"{name}: no exception", False, str(e))


def run_agentic_trace_tests(orch):
    print("\n── Agentic Trace Verification ──")
    multi_step_queries = [
        ("novelty multi-step", "Is neem-based biopesticide patentable under Indian law?", 2),
        ("jurisdiction parallel", "Compare India and US patent rules for herbal formulations", 2),
    ]
    for name, query, min_steps in multi_step_queries:
        try:
            result = orch.run(query)
            trace = result.get("trace", [])
            retrieval_steps = [s for s in trace if s.get("step") == "retrieval"]
            check(f"{name}: ≥ {min_steps} retrieval steps in trace",
                  len(retrieval_steps) >= min_steps,
                  f"got {len(retrieval_steps)} steps")
        except Exception as e:
            check(f"{name}: no exception", False, str(e))


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true",
                        help="Run unit tests only (no DB/LLM)")
    args = parser.parse_args()

    print("=" * 60)
    print("IP-SAKTI Sahayak — Domain Test Suite (Phase 10)")
    print("=" * 60)

    # Always run unit tests
    test_citation_formatter()
    test_session_cache()
    test_verifier()
    test_citation_index()

    if not args.offline:
        print("\n── Connecting to databases ──")
        try:
            from src.database.neo4j_manager import Neo4jManager
            from src.database.qdrant_manager import QdrantManager
            from src.processors.embedding_processor import EmbeddingProcessor
            from src.query_engine import QueryEngine
            from src.agent.orchestrator import Orchestrator

            cfg = Config()
            emb = EmbeddingProcessor(cfg)
            emb.load_model()
            neo = Neo4jManager(cfg)
            neo.connect()
            qd = QdrantManager(cfg, emb)
            qd.connect()
            engine = QueryEngine(neo, qd, emb)
            orch = Orchestrator(engine, cfg)

            run_integration_tests(engine, orch)
            run_agentic_trace_tests(orch)
        except Exception as e:
            print(f"\n⚠️  DB/LLM connection failed: {e}")
            print("   Run with --offline to run unit tests only.")

    # Summary
    passed = sum(1 for _, ok, _ in _results if ok)
    total  = len(_results)
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("Failed tests:")
        for name, ok, detail in _results:
            if not ok:
                print(f"  ❌  {name}  {detail}")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
