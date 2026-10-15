"""
IP-SAKTI RAG Evaluation — LLM-as-Judge (RAGAS-equivalent metrics)
===================================================================
Self-contained: uses only the openai SDK (already in venv) + your Groq key.
No ragas package needed — we implement the same 5 metric prompts directly.

Metrics (all 0-1, higher = better):
  faithfulness       – are claims in the answer supported by retrieved context?
  answer_relevancy   – does the answer actually address the question?
  context_precision  – are the retrieved chunks relevant to the question?
  context_recall     – does the retrieved context cover the reference answer?
  answer_correctness – does the answer match the reference answer semantically?

Run:
    python evaluate_rag.py
"""

import os, sys, json, time, re
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv()

# ── Judge LLM (Groq via OpenAI compat) ───────────────────────────────────────
from openai import OpenAI

API_KEY  = os.environ["SYNTHESIS_LLM_API_KEY"]
BASE_URL = os.getenv("SYNTHESIS_LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL    = os.getenv("SYNTHESIS_LLM", "llama-3.1-8b-instant")

judge = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def _judge(prompt: str, retries: int = 4) -> str:
    """Call judge LLM; return text. Retry on rate-limit."""
    for attempt in range(retries):
        try:
            r = judge.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=64,
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait = 8 * (attempt + 1)
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return f"ERROR:{e}"

def _parse_score(text: str) -> float:
    """Extract first float in [0,1] from LLM output."""
    m = re.search(r"(\d+\.?\d*)", text)
    if not m:
        return float("nan")
    v = float(m.group(1))
    if v > 1:          # model returned 0-10 scale
        v /= 10.0
    return max(0.0, min(1.0, v))

# ── RAGAS-equivalent metric prompts ──────────────────────────────────────────

def faithfulness(question, answer, contexts):
    """Fraction of answer claims supported by context."""
    ctx = "\n".join(f"[C{i+1}] {c[:400]}" for i, c in enumerate(contexts[:6]))
    p = (
        f"Context:\n{ctx}\n\nAnswer:\n{answer}\n\n"
        "Score how faithfully the Answer is grounded in the Context. "
        "Only count claims that are directly supported by the Context. "
        "Respond with a single decimal number from 0.0 (no support) to 1.0 (fully supported). "
        "No explanation."
    )
    return _parse_score(_judge(p))

def answer_relevancy(question, answer, contexts):
    """Does the answer address the question?"""
    p = (
        f"Question: {question}\n\nAnswer:\n{answer}\n\n"
        "Score how relevant and complete the Answer is to the Question. "
        "Respond with a single decimal from 0.0 (irrelevant) to 1.0 (perfectly relevant). "
        "No explanation."
    )
    return _parse_score(_judge(p))

def context_precision(question, contexts, reference):
    """Are the retrieved chunks relevant to answering the question?"""
    relevant = 0
    for c in contexts[:6]:
        p = (
            f"Question: {question}\n\nChunk:\n{c[:400]}\n\n"
            "Is this chunk useful for answering the question? "
            "Respond with 1 (useful) or 0 (not useful). No explanation."
        )
        score = _parse_score(_judge(p))
        if score >= 0.5:
            relevant += 1
    return relevant / max(1, len(contexts[:6]))

def context_recall(question, contexts, reference):
    """Does the retrieved context cover the information in the reference answer?"""
    ctx = "\n".join(f"[C{i+1}] {c[:400]}" for i, c in enumerate(contexts[:6]))
    p = (
        f"Context:\n{ctx}\n\nReference Answer:\n{reference}\n\n"
        "Score what fraction of the Reference Answer's information is present in the Context. "
        "Respond with a single decimal from 0.0 (nothing covered) to 1.0 (fully covered). "
        "No explanation."
    )
    return _parse_score(_judge(p))

def answer_correctness(question, answer, reference):
    """Factual + semantic similarity to the reference answer."""
    p = (
        f"Question: {question}\n\nGenerated Answer:\n{answer}\n\nReference Answer:\n{reference}\n\n"
        "Score how correct the Generated Answer is compared to the Reference Answer. "
        "Consider factual accuracy and completeness. "
        "Respond with a single decimal from 0.0 (completely wrong) to 1.0 (perfect). "
        "No explanation."
    )
    return _parse_score(_judge(p))

# ── Evaluation dataset ────────────────────────────────────────────────────────
EVAL_DATASET = [
    {
        "question": "Is turmeric patentable in India under the Patents Act?",
        "reference": (
            "No. Turmeric is not patentable under Section 3(p) of the Patents Act 1970, "
            "which bars patents on traditional knowledge. The 1997 USPTO patent was revoked "
            "after CSIR cited Ayurvedic prior art from the TKDL."
        ),
    },
    {
        "question": "What approvals are required before commercialising an Ayurvedic formulation using a Schedule I plant under the Biological Diversity Act?",
        "reference": (
            "Prior approval from the National Biodiversity Authority (NBA) is mandatory "
            "under Section 6 of the Biological Diversity Act 2002 before any IPR application "
            "or commercial use. State Biodiversity Board permission may also be needed."
        ),
    },
    {
        "question": "How does Section 3(p) of the Indian Patents Act protect traditional knowledge?",
        "reference": (
            "Section 3(p) bars patents for inventions that are traditional knowledge or "
            "aggregations of known properties of traditionally known components, preventing "
            "biopiracy of Ayurvedic formulations documented in classical texts."
        ),
    },
    {
        "question": "What is the TKDL and how does it help prevent biopiracy?",
        "reference": (
            "The Traditional Knowledge Digital Library (TKDL) is a government database of "
            "over 0.29 million Ayurvedic, Unani, and Siddha formulations digitised from "
            "classical texts, accessible to international patent offices as prior-art documentation."
        ),
    },
    {
        "question": "Under what conditions can an Ayurvedic product be exported to the EU as a herbal medicinal product?",
        "reference": (
            "EU THMPD (2004/24/EC) requires 30 years of traditional use (at least 15 in the EU), "
            "a safety dossier, and registration with national competent authorities. "
            "GMP compliance and bibliographic evidence of use are mandatory; no clinical trials required."
        ),
    },
    {
        "question": "What is the Nagoya Protocol and what obligations does it create for Ayurvedic researchers?",
        "reference": (
            "The Nagoya Protocol (2010) under the CBD requires Prior Informed Consent (PIC) "
            "from the country of origin and fair benefit-sharing (mutually agreed terms) "
            "with local communities when accessing genetic resources or traditional knowledge."
        ),
    },
    {
        "question": "Can a geographical indication protect an Ayurvedic product like Kashmiri Saffron?",
        "reference": (
            "Yes. The Geographical Indications of Goods Act 1999 protects products tied to "
            "specific geographic origin. Kashmiri Saffron holds a GI tag, preventing other "
            "regions from misrepresenting their products under that name."
        ),
    },
    {
        "question": "What GMP certification is required for an AYUSH manufacturing licence?",
        "reference": (
            "GMP certification under Schedule T of the Drugs and Cosmetics Act 1940 is "
            "mandatory for an AYUSH manufacturing licence. Standards cover premises, equipment, "
            "raw material testing, quality control, and record-keeping."
        ),
    },
    {
        "question": "What was the significance of the Neem patent revocation case for biopiracy law?",
        "reference": (
            "The EPO revoked EP 436257 on neem biopesticide in 2000 after India demonstrated "
            "centuries of prior use. It established that TKDL-backed prior-art citations can "
            "successfully invalidate traditional-knowledge patents."
        ),
    },
    {
        "question": "How does the Charaka Samhita serve as prior art in patent disputes?",
        "reference": (
            "The Charaka Samhita documents Ayurvedic formulations centuries old; patent offices "
            "treat classical text citations as prior-art evidence. TKDL digitised these in five "
            "languages so examiners worldwide can cite them to reject biopiracy-based patents."
        ),
    },
    {
        "question": "What are the key differences in IP protection between India and the US for herbal formulations?",
        "reference": (
            "India: Section 3(p) bars traditional knowledge patents; TKDL provides prior-art "
            "database; BDA 2002 requires NBA approval. US: No equivalent TK database; "
            "dietary supplements under DSHEA 1994 need no pre-market approval; botanical drugs "
            "need full NDA under 21 CFR 314."
        ),
    },
    {
        "question": "What procedural steps must an MSME follow to file for patent protection on a novel Ayurvedic formulation?",
        "reference": (
            "Step 1: TKDL prior-art search. Step 2: NBA approval under BDA Section 6 if using "
            "listed biological resources. Step 3: File provisional specification at Indian Patent "
            "Office. Step 4: Respond to examination objections. "
            "Step 5: File complete specification within 12 months of provisional."
        ),
    },
]

# ── Pipeline init ─────────────────────────────────────────────────────────────
def build_pipeline():
    from src.config import Config
    from src.database.neo4j_manager import Neo4jManager
    from src.database.qdrant_manager import QdrantManager
    from src.processors.embedding_processor import EmbeddingProcessor
    from src.query_engine import QueryEngine

    cfg = Config()

    neo4j = Neo4jManager(cfg)
    neo4j.connect()

    # Must load_model() before passing to QdrantManager (mirrors api.py lifespan)
    emb = EmbeddingProcessor(cfg)
    emb.load_model()

    qdrant = QdrantManager(cfg, embedding_model=emb)
    qdrant.connect()

    return QueryEngine(neo4j, qdrant, embedding_processor=emb)

# ── Collect answers from the live pipeline ────────────────────────────────────
def collect_samples(engine):
    samples = []
    print(f"\n{'='*62}", flush=True)
    print(f"  Querying live pipeline — {len(EVAL_DATASET)} questions", flush=True)
    print(f"{'='*62}\n", flush=True)

    for i, item in enumerate(EVAL_DATASET, 1):
        q, ref = item["question"], item["reference"]
        print(f"[{i:02d}/{len(EVAL_DATASET)}] {q[:65]}...", flush=True)
        t0 = time.time()
        try:
            result   = engine.generate_answer(q, limit=6)
            elapsed  = time.time() - t0
            answer   = result.get("answer", "")
            # Reuse retrieved contexts directly from the engine result
            contexts = [s.get("source_snippet") or s.get("text", "") for s in result.get("sources", []) if (s.get("source_snippet") or s.get("text"))]
            if not contexts and result.get("context"):
                contexts = [result["context"]]
            samples.append({"question": q, "reference": ref,
                             "answer": answer, "contexts": contexts,
                             "elapsed": round(elapsed, 2), "error": None})
            print(f"        OK  {elapsed:.1f}s  tags={result.get('tags', [])}", flush=True)
        except Exception as e:
            elapsed = time.time() - t0
            print(f"        ERR {e}", flush=True)
            samples.append({"question": q, "reference": ref,
                             "answer": "", "contexts": [],
                             "elapsed": elapsed, "error": str(e)})
        time.sleep(1.0)
    return samples

# ── Score each sample with all 5 metrics ─────────────────────────────────────
def score_samples(samples):
    metric_names = ["faithfulness", "answer_relevancy",
                    "context_precision", "context_recall", "answer_correctness"]
    for s in samples:
        if s["error"]:
            s["scores"] = {m: float("nan") for m in metric_names}
            continue

        q, a, ctx, ref = s["question"], s["answer"], s["contexts"], s["reference"]
        print(f"\n  Scoring: {q[:55]}...", flush=True)
        s["scores"] = {
            "faithfulness":       faithfulness(q, a, ctx),
            "answer_relevancy":   answer_relevancy(q, a, ctx),
            "context_precision":  context_precision(q, ctx, ref),
            "context_recall":     context_recall(q, ctx, ref),
            "answer_correctness": answer_correctness(q, a, ref),
        }
        sc = s["scores"]
        print(f"    F={sc['faithfulness']:.2f}  AR={sc['answer_relevancy']:.2f}  "
              f"CP={sc['context_precision']:.2f}  CR={sc['context_recall']:.2f}  "
              f"AC={sc['answer_correctness']:.2f}", flush=True)
        time.sleep(1.0)   # pace requests to stay well within Groq rate limits
    return samples

# ── Report ────────────────────────────────────────────────────────────────────
def report(samples):
    metric_names = ["faithfulness", "answer_relevancy",
                    "context_precision", "context_recall", "answer_correctness"]
    labels = {
        "faithfulness":       "Faithfulness        ",
        "answer_relevancy":   "Answer Relevancy    ",
        "context_precision":  "Context Precision   ",
        "context_recall":     "Context Recall      ",
        "answer_correctness": "Answer Correctness  ",
    }

    valid = [s for s in samples if not s["error"]]
    avgs  = {}
    for m in metric_names:
        vals = [s["scores"][m] for s in valid if not __import__("math").isnan(s["scores"][m])]
        avgs[m] = sum(vals) / len(vals) if vals else float("nan")

    overall = sum(v for v in avgs.values() if not __import__("math").isnan(v)) / \
              sum(1 for v in avgs.values() if not __import__("math").isnan(v))

    avg_latency = sum(s["elapsed"] for s in valid) / max(1, len(valid))

    print("\n" + "="*62, flush=True)
    print("  IP-SAKTI Sahayak — GraphRAG Evaluation Results", flush=True)
    print("="*62, flush=True)
    print(f"  Model under test  : Hybrid GraphRAG (Neo4j + Qdrant + Groq)", flush=True)
    print(f"  Judge LLM         : {MODEL} via Groq", flush=True)
    print(f"  Samples evaluated : {len(valid)}/{len(samples)}", flush=True)
    print(f"  Avg query latency : {avg_latency:.2f}s", flush=True)
    print("", flush=True)

    for m, label in labels.items():
        v = avgs[m]
        bar_filled = int(v * 30)
        bar = "#" * bar_filled + "-" * (30 - bar_filled)
        pct = v * 100
        print(f"  {label}: {v:.4f}  [{bar}]  {pct:.1f}%", flush=True)

    print("", flush=True)
    overall_bar = "#" * int(overall * 30) + "-" * (30 - int(overall * 30))
    print(f"  OVERALL RAG SCORE : {overall:.4f}  [{overall_bar}]  {overall*100:.1f}%", flush=True)
    print("="*62, flush=True)

    # Save JSON
    out = {
        "project": "IP-SAKTI Sahayak — Agentic GraphRAG for Ayurvedic IP",
        "judge_model": MODEL,
        "samples_evaluated": len(valid),
        "avg_latency_s": round(avg_latency, 2),
        "metrics": {m: round(avgs[m], 4) for m in metric_names},
        "overall_score": round(overall, 4),
        "per_question": [
            {
                "question": s["question"],
                "elapsed_s": s["elapsed"],
                "scores": {k: round(v, 4) for k, v in s["scores"].items()},
                "error": s["error"],
            }
            for s in samples
        ],
    }

    report_path = ROOT / "rag_evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Saved full report -> {report_path}\n", flush=True)
    return out

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Initialising pipeline...", flush=True)
    try:
        engine = build_pipeline()
    except Exception as e:
        print(f"ERROR: Cannot start pipeline: {e}", flush=True)
        print("Ensure docker compose up -d is running.", flush=True)
        sys.exit(1)

    samples = collect_samples(engine)

    print(f"\n{'='*62}", flush=True)
    print("  Running LLM-as-judge scoring (RAGAS-equivalent metrics)...", flush=True)
    print(f"{'='*62}", flush=True)
    samples = score_samples(samples)
    report(samples)
