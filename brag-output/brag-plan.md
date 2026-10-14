# Brag Plan: GraphRAG (IP-SAKTI Sahayak)

## What is this app?
GraphRAG (IP-SAKTI Sahayak) is an enterprise-grade, multilingual, agentic Knowledge Graph & RAG system built for SIH 2026 (Ministry of AYUSH) that unifies Neo4j property graphs with Qdrant vector retrieval to defend traditional Ayurvedic intellectual property, resolve complex cross-border patent statutes, and eliminate hallucinations with sub-5ms deterministic verification.

## The angle
Standard vector RAG fails catastrophically on multi-hop legal reasoning—it hallucinates patent clearances and misses statutory penalties like mandatory National Biodiversity Authority (NBA) Section 6 approvals. GraphRAG solves this by traversing 11,568 ontology nodes and 23,313 legal edges across Indian Statutes, TKDL, USPTO, EPO, and the Nagoya Protocol with a 5-mode agentic router and sub-5ms post-generation n-gram verifier.

## Hook (first 2-3 seconds)
"5,000 Years of Ayurvedic Wisdom. Trapped in a Legal Blindspot." A dramatic high-contrast split-screen showcasing classical formulation manuscripts contrasted against international patent revocation disputes (Turmeric & Neem biopiracy), asking: *Why does standard vector search fail at protecting traditional knowledge?*

## Key moments (the middle)
- **The Problem: The Vector-Only Trap**: Vector search pulls keywords but misses non-obvious multi-hop statutory rules (e.g. Biological Diversity Act Sec 6 prior approval required before foreign filing).
- **The Dual-Engine Core**: Side-by-side architectural powerhouse: Neo4j 5.18 Property Graph (11,568 nodes, 23,313 edges) fused with Qdrant Vector DB (11,534 1024-dim dense vectors).
- **Live Multi-Hop Traversal**: Step-by-step visual graph walk for *Nisha Amalaki*: `(Formulation) ➔ (Curcuma longa) ➔ (TKDL) ➔ (Patents Act Sec 3(p) Exclusion) ➔ (NBA Section 6 Approval)`.
- **5-Mode Agentic Router**: Specialized reasoning modes (`novelty_check`, `jurisdiction_comparison`, `precedent_lookup`, `procedural`, `general`) with Cerebras sub-100ms classification.
- **Zero Hallucination Guardrail**: Sub-5ms runtime n-gram overlap verifier with tri-level confidence badges: `[CLEAR]`, `[INFERRED]`, `[AMBIGUOUS]`.
- **Omnichannel Access**: Interactive Web UI with real-time waveform visualizer, Hindi speech-to-speech with smart barge-in (`faster-whisper` + `Kokoro-ONNX`), Twilio WhatsApp bot, and native Model Context Protocol (MCP) server.

## Outro / punchline
"Defending Heritage. Accelerating Global Innovation."
IP-SAKTI Sahayak · Smart India Hackathon 2026 · Ministry of AYUSH.

## User flow worth showing
1. User asks: *"Can I patent a Nisha Amalaki formulation in the US, and what approvals are required?"*
2. System activates 5-mode router (`novelty_check` + `procedural`) & traverses Neo4j property edges to Indian Patents Act Sec 3(p) and Biodiversity Act Sec 6.
3. Post-generation verifier verifies every claim against retrieved text in sub-5ms, outputting grounded legal citations with `[CLEAR]` badges and procedural steps.

## Tone
- Preset: `cinematic`
- Creative direction: Dramatic, high-craft, intellectual property defense product launch.
- Interpretation: Deep, authoritative botanical colors, fluid transitions, crisp typography, rhythmic beat pacing, bold claims backed by concrete metrics.

## Format: landscape — 1920x1080
## Duration: 55s

## Visual identity (from the project)
- Background: `#0B1A15` (Deep Botanical Dark) / `#134A3F` (Primary Emerald) / `#FBFAF7` (Canvas Light)
- Accent: `#E28D38` (Saffron Gold) / `#34D399` (Mint Green) / `#4B5A28` (Olive)
- Text: `#FFFFFF` / `#E7E6D8` (Warm Cream) / `#839581` (Sage Muted)
- Display font: Plus Jakarta Sans
- Body font: Inter
- Strongest visual element: Dual-Engine Knowledge Graph Topology, Neo4j multi-hop node connectors, and the tri-level confidence badges (`[CLEAR]` / `[INFERRED]`).

## Share copy (draft)
5,000 years of Ayurveda meets dual-engine GraphRAG. Defending traditional knowledge with 11,568 graph nodes, 23,313 legal edges, and sub-5ms zero-hallucination verification. Built for SIH 2026.

## Audio direction
- Role: Cinematic momentum and rhythmic beats.
- Music: `happy-beats-business-moves-vol-10-by-ende-dot-app.mp3` (60s energetic, driving track with modern punch).
- Music treatment: Starts clear at t=0, builds energy through the architectural reveals, swells at the multi-hop traversal, and smoothly ducks under final branding.
- Music cue guidance: Major beat transitions at ~8s, ~17s, ~27s, ~38s, ~48s.
- Audio-reactive treatment: Subtle ambient glow and card border pulse synced with musical energy.
- SFX posture: Crisp UI clicks, subtle interface transitions, and heavy resonance hits on major revelations.

## Storyboard

### Scene 1 — The Biopiracy Crisis & The Patent Trap — 0.0s to 8.0s (8s)
- **Visuals**: Dark cinematic opening. Glowing text: "5,000 YEARS OF TRADITIONAL KNOWLEDGE". Headline drops: "TRAPPED IN A GLOBAL LEGAL BLINDSPOT".
- **Problem Statement**:
  - Unlawful foreign patents on sacred heritage (Turmeric & Neem revocations).
  - The Vector-Only Failure: Traditional vector RAG suffers from context fragmentation, misses multi-hop statutory dependencies, and hallucinates regulatory compliance.
- **Audio intent**: Dramatic tension, crisp interface sweep.
- **Transition**: Dynamic wipe into Scene 2.

### Scene 2 — The Dual-Engine Architecture — 8.0s to 17.0s (9s)
- **Visuals**: Title reveals: "GRAPH-RAG · DUAL-ENGINE INTELLIGENCE".
- **Left Column**: Neo4j 5.18 Enterprise Property Graph — 11,568 Nodes, 23,313 Edges (Hierarchical, Sequential & Relational).
- **Right Column**: Qdrant Vector DB — 11,534 Dense Vectors (1024-d `multilingual-e5-large`), Structure-Aware Chunking.
- **Center**: "Unified Symbolic Traversal + Semantic Embedding".
- **Audio intent**: Driving bass kick, technical confidence.
- **Transition**: Smooth camera push into Scene 3.

### Scene 3 — Multi-Hop Knowledge Traversal — 17.0s to 27.0s (10s)
- **Visuals**: "LIVE MULTI-HOP LEGAL REASONING".
- **Real-World Case Walk**:
  - Node 1: `[Formulation: Nisha Amalaki]` ➔
  - Node 2: `[Ingredient: Curcuma longa]` ➔
  - Node 3: `[LegalInstrument: TKDL Prior Art]` ➔
  - Node 4: `[Patents Act 1970: Section 3(p) Non-Patentability]` ➔
  - Node 5: `[Biological Resource: NBA Section 6 Mandatory Foreign Approval]`
- **Statute Integration**: Cross-referencing Indian Patents Act, Biological Diversity Act 2002, and Nagoya Protocol.
- **Audio intent**: Rhythmic sync with node appearances, interface pings.
- **Transition**: Perspective shift into Scene 4.

### Scene 4 — 5-Mode Agentic Router & Zero-Hallucination Guardrails — 27.0s to 38.0s (11s)
- **Visuals**: "AGENTIC ORCHESTRATION & DETERMINISTIC VERIFICATION".
- **Top Matrix**: 5-Mode Intent Classifier:
  - `novelty_check` · `jurisdiction_comparison` · `precedent_lookup` · `procedural` · `general`
- **Bottom Feature**: Post-Generation Verifier (`verifier.py`):
  - Sub-5ms n-gram string overlap check.
  - Tri-level confidence stamping: `[CLEAR]` (Direct statutory proof), `[INFERRED]`, `[AMBIGUOUS]`.
  - Automatic refusal guardrail: "Strictly Grounded. Zero Hallucination."
- **Audio intent**: Fast rhythmic pulse, positive chime on `[CLEAR]` verification badge.
- **Transition**: Card flip into Scene 5.

### Scene 5 — Omnichannel Accessibility & Voice Engine — 38.0s to 48.0s (10s)
- **Visuals**: "ACCESSIBLE TO RESEARCHERS, RURAL HEALERS & AGENTS".
- **4 Grid Pillars**:
  1. **Interactive Web UI**: Real-time Web Audio API waveform visualizer, clickable citation provenance cards.
  2. **Bidirectional Voice**: High-precision `Faster-Whisper` + `Kokoro-ONNX` neural TTS with smart barge-in interruption.
  3. **Conversational WhatsApp Bot**: Twilio webhook integration for direct mobile farmer & practitioner access.
  4. **Native MCP Server**: First-class Model Context Protocol tools (`graphrag_query`, `get_session_history`) for AI coding agents.
- **Audio intent**: Warm, uplifting technological harmony.
- **Transition**: Cinematic dissolve into Grand Finale.

### Scene 6 — Grand Finale & Impact — 48.0s to 55.0s (7s)
- **Visuals**: Hero Emblem:
  - "IP-SAKTI SAHAYAK"
  - "Dual-Engine GraphRAG for Ayurveda & Traditional Knowledge"
  - "Smart India Hackathon 2026 · Ministry of AYUSH"
  - Badges: `Neo4j 5.18` · `Qdrant` · `FastAPI` · `Faster-Whisper` · `Kokoro` · `MCP` · `MIT License`
- **Audio intent**: Grand musical crescendo, settling into pure brand clarity.
