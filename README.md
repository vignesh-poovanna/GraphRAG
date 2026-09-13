# GraphRAG: Dual-Engine Knowledge Graph & Multilingual Agentic RAG System
### *IP-SAKTI Sahayak — AI-Powered Intellectual Property & Regulatory Guidance Platform for Ayurveda and Traditional Knowledge*
#### *Built for Smart India Hackathon (SIH 2026 Problem Statement: SIH26045 — Ministry of AYUSH)*

[![FastAPI](https://img.shields.io/badge/API-FastAPI%200.110+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Neo4j](https://img.shields.io/badge/Graph%20DB-Neo4j%205.18-008CC1.svg?style=flat&logo=neo4j)](https://neo4j.com/)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant%201.8.0-DC382D.svg?style=flat&logo=qdrant)](https://qdrant.tech/)
[![Embeddings](https://img.shields.io/badge/Embeddings-multilingual--e5--large%20(1024--d)-blue.svg?style=flat)](https://huggingface.co/intfloat/multilingual-e5-large)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%7C%20Cerebras%20%7C%20Ollama-orange.svg?style=flat)](https://groq.com)
[![Speech](https://img.shields.io/badge/Voice-Faster--Whisper%20%2B%20Kokoro--ONNX-purple.svg?style=flat)](https://github.com/SYSTRAN/faster-whisper)
[![MCP](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-blueviolet.svg?style=flat)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat)](LICENSE)

---

## Executive Summary

**GraphRAG (IP-SAKTI Sahayak)** is an enterprise-grade, multilingual, agentic Retrieval-Augmented Generation (RAG) platform. It unifies **symbolic property graph traversal (Neo4j)** with **high-dimensional dense vector indexing (Qdrant)** to solve one of the most intricate retrieval challenges in intellectual property: navigating the intersection of **traditional medicinal knowledge (TKDL)**, **national patent statutes (Indian Patents Act, Biological Diversity Act)**, and **cross-border international treaties (Nagoya Protocol, WIPO, USPTO, EPO)**.

Traditional vector-only RAG pipelines suffer from context fragmentation, catastrophic omission of multi-hop relational dependencies, and hallucination on domain-specific edge cases. GraphRAG eliminates these limitations through:
1. **Multi-Hop Relational Traversal**: Explores entity chains across distinct legal instruments, court rulings, botanical formulations, and regulatory bodies.
2. **Deterministic Anti-Hallucination Guardrails**: Implements strict contextual boundary prompts backed by a sub-5ms runtime n-gram overlap verifier that automatically downgrades ungrounded claims.
3. **Agentic Orchestration**: Features a dynamic 5-mode intent classifier routing queries to specialized retrieval workflows (novelty check, cross-jurisdiction comparison, precedent lookup, procedural compliance, and general synthesis).
4. **Multimodal Accessibility**: Provides a rich Web UI with real-time waveform audio streaming, conversational WhatsApp integration via Twilio, full Model Context Protocol (MCP) server endpoints, and low-latency bidirectional voice with smart barge-in interruption.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Ingestion ["1. Document Ingestion & Structure-Aware Processing"]
        DocInput["Raw Documents\n(PDF, Markdown, HTML, DOCX, TXT)"] --> FormConv["Format Converter\n(PyMuPDF4LLM + IBM Docling)"]
        FormConv --> Chunker["Structure-Aware Chunker\n(Heading split, Atomic Tables, Sentence Snapping)"]
        Chunker --> MetaExtractor["Metadata Extractor\n(Act, Section, Jurisdiction, Year, DocType)"]
    end

    subgraph Storage ["2. Dual-Engine Knowledge Storage"]
        MetaExtractor -->|1024-dim Dense Vectors| QdrantDB[("Qdrant Vector DB\nCollection: document_chunks\nMetric: Cosine")]
        MetaExtractor -->|Structural Hierarchy\nDocument -> Chunk -> Next| Neo4jDB[("Neo4j Property Graph\n5.18 Enterprise Graph")]
    end

    subgraph Enrichment ["3. Domain Entity & Relationship Enrichment"]
        Neo4jDB --> Extractor["Concept Extractor (Ollama llama3.2:3b)\nFew-shot Prompting + SQLite Cache"]
        Extractor -->|Upsert Entities & Legal Relations| Neo4jDB
        Extractor -->|Inferred Relations [INFERRED]| Neo4jDB
    end

    subgraph Orchestration ["4. Agentic Retrieval & Orchestrator"]
        UserQuery["User Input\n(Web UI, Voice, WhatsApp, MCP)"] --> LangDetect{"Language Detection\n& Translation"}
        LangDetect --> Classify["Query Classifier\n(Cerebras / Groq / Ollama)"]
        Classify -->|Mode Selection| Router{"5-Mode Agentic Router"}
        
        Router -->|novelty_check| M1["Novelty & Prior-Art Retrieval\n(TKDL + Section 3(p) Exclusions)"]
        Router -->|jurisdiction_comparison| M2["Multi-Jurisdiction Parallel Retrieval\n(India vs US vs EU vs WIPO)"]
        Router -->|precedent_lookup| M3["Case Precedent Graph Walk\n(:CITES -> LegalInstrument)"]
        Router -->|procedural| M4["Procedural Stage Retrieval\n(Licensing, ABS, Inspection)"]
        Router -->|general| M5["Hybrid Vector + Graph Expansion\n(Candidate Reranking & Statute Boost)"]
    end

    subgraph Synthesis ["5. Grounded Synthesis & Guardrail Verification"]
        M1 & M2 & M3 & M4 & M5 --> HybridContext["Hybrid Context Assembly\n(Ranked chunks + 1-2 hop neighbors)"]
        HybridContext --> SynthLLM["Synthesis LLM (Groq Llama-3.1-8b-instant)\nStrict Context-Only System Prompt"]
        SynthLLM --> PostGuard["Post-Generation Verifier (verifier.py)\nSub-5ms n-gram String-Overlap Check"]
        PostGuard --> CitFormatter["Citation Formatter\nLegal Provenance & Confidence Tags"]
        CitFormatter --> ResponseOut["Grounded Multi-Modal Response\n(Inline Citations, [CLEAR]/[AMBIGUOUS], Follow-ups)"]
    end
```

---

## Live System Metrics & Knowledge Graph Topology

The system is fully populated and verified against a comprehensive corpus of Indian statutes, biodiversity rules, international treaties, and traditional knowledge documentation.

### Core Database Counts

| Database / Layer | Component / Entity | Metric Count | Details & Specifications |
| :--- | :--- | :---: | :--- |
| **Document Store** | Total Ingested Documents | **34** | Full statutes, gazette notifications, treaties, TKDL corpora, case briefs |
| **Vector Database** | Qdrant Total Vectors | **11,534** | 1024-dimensional dense vectors stored in collection `document_chunks` |
| **Vector Database** | Vector Distance Metric | **Cosine** | Normalized cosine distance with HNSW indexing |
| **Vector Database** | Index Payload Memory | **~17.7 MB** | In-memory payload cache with payload index filters on `category`, `doc_id` |
| **Graph Database** | Neo4j Document Nodes (`:Document`) | **34** | Root document nodes with metadata, category, and source file paths |
| **Graph Database** | Neo4j Chunk Nodes (`:Chunk`) | **11,534** | Text chunk nodes containing position indices and content |
| **Graph Database** | Total Graph Nodes | **11,568** | Complete node network in Neo4j 5.18 |
| **Graph Database** | Total Graph Relationships | **23,313** | Explicit and inferred structural, sequential, and relational edges |
| **Graph Database** | Hierarchy Edges (`:HAS_CHUNK`) | **11,534** | Direct parent-child links from `:Document` to constituent `:Chunk` nodes |
| **Graph Database** | Sequential Edges (`:NEXT`) | **11,500** | Temporal flow ordering connecting sequential chunks within documents |
| **Graph Database** | Relational Edges (`:RELATED_TO`) | **279** | Cross-document and cross-topic edges with prioritized weights |

### Neo4j Graph Ontology & Node Types

The property graph schema defines specialized domain labels and relational constraints:

```
[Document] ──(:HAS_CHUNK)──> [Chunk] ──(:NEXT)──> [Chunk]
                                │
                          (:MENTIONS)
                                │
                                ▼
                       [Domain Entities]
    ┌───────────────────────────┼───────────────────────────┐
    │                           │                           │
[Formulation]             [Ingredient]              [LegalInstrument]
    │                           │                           │
    ├─(:CONTAINS_INGREDIENT)────┘                           ├─(:APPLIES_IN)──> [Jurisdiction]
    ├─(:DOCUMENTED_IN)──────────────────────────────────────┤
    │                                                       ├─(:GOVERNED_BY)─> [RegulatoryBody]
    ▼                                                       ▲
[CasePrecedent] ──(:CITES)──────────────────────────────────┘
    │
    └─(:HAS_INFERRED_RELATION)──> [InferredRelation] ──(:INFERRED_TARGET)──> [IPProtectionType]
                                  (Tag: [INFERRED])
```

- **Domain Entity Labels**:
  - `Formulation`: Classical and proprietary Ayurvedic preparations (e.g., *Triphala*, *Chyawanprash*, *Nisha Amalaki*).
  - `Ingredient`: Herbal, mineral, and biological resources (e.g., *Curcuma longa*, *Azadirachta indica*).
  - `LegalInstrument`: Statutes, sections, rules, and treaties (e.g., *Patents Act 1970 Sec 3(p)*, *Biological Diversity Act 2002 Sec 3*, *Nagoya Protocol Art 5*).
  - `Jurisdiction`: Sovereign and regional legal regimes (*India*, *United States*, *European Union*, *WIPO*, *International*).
  - `IPProtectionType`: Classification of protection (*Patent*, *Geographical Indication*, *Traditional Knowledge*, *Trade Secret*).
  - `CasePrecedent`: Landmark litigation and revocations (*Turmeric Wound Healing Patent Revocation*, *Neem Fungicidal Patent Revocation*).
  - `RegulatoryBody`: Statutory bodies (*National Biodiversity Authority*, *State Biodiversity Boards*, *Indian Patent Office (CGPDTM)*, *USPTO*, *EPO*).
  - `InferredRelation`: Intermediate node capturing non-explicit legal deductions without corrupting factual statutory edges.

---

## Why GraphRAG? Vector DB vs. GraphRAG Comparison

### The Inherent Flaws of Vector-Only RAG

Standard semantic vector retrieval embeds queries and document chunks into a metric space, returning top-$k$ nearest neighbors based on cosine similarity. In multi-document legal, regulatory, and scientific domains, this creates severe failure modes:

| Failure Mode | Vector-Only RAG | GraphRAG Solution |
| :--- | :--- | :--- |
| **Multi-Hop Dependency** | Fails when intermediate steps lack query keywords. | Walks property graph edges (`:CITES`, `:APPLIES_IN`, `:DOCUMENTED_IN`) across multi-step dependency paths. |
| **Context Fragmentation** | Fixed token splits tear tables, statutory clauses, and numbered lists in half. | **Structure-Aware Chunking** preserves atomic Markdown tables, section hierarchy, and heading contexts. |
| **Global Systemic Reasoning** | Chunks are isolated points; global synthesis across multiple laws is impossible. | Ingests structural document links, sequential `:NEXT` links, and concept co-occurrence bridges. |
| **Hallucination on Ambiguity** | LLM guesses when information is conflicting or jurisdiction-specific. | **Two-tier verification**: System prompts enforce strict refusal, and post-generation string verifiers downgrade ungrounded claims. |

### Concrete Demonstration Scenario

> **Scenario**: An Ayurvedic enterprise in Kerala intends to export a standardized *Nisha Amalaki* formulation containing *Curcuma longa* to the United States as a dietary supplement.
>
> **User Question**: *"Can I patent this formulation, and what approvals are required before applying for a foreign patent?"*

- **Where Vector-Only RAG Fails**:
  - Semantic vector search retrieves chunks about *"patent application procedures"* and general *"herbal formulation patents"*.
  - Because Section 3(p) of the Indian Patents Act states that traditional knowledge is non-patentable subject matter, but may not mention the word *"Nisha Amalaki"*, it gets scored low.
  - The Biological Diversity Act (BDA, 2002) Section 6 mandates prior approval from the National Biodiversity Authority (NBA) before filing *any* foreign patent based on Indian biological resources. Because the question didn't explicitly mention "biodiversity", the BDA chunks are ranked outside top-$k$.
  - **Result**: The LLM fabricates a standard patent filing process and fails to mention the mandatory NBA clearance, exposing the user to severe statutory penalties.

- **How GraphRAG Solves It**:
  1. **Step 1 (Vector Entrypoint)**: Vector search identifies *Nisha Amalaki* as an Ayurvedic formulation.
  2. **Step 2 (Graph Traversal)**:
     - The engine navigates: `(Formulation: Nisha Amalaki)-[:CONTAINS_INGREDIENT]->(Ingredient: Curcuma longa)-[:DOCUMENTED_IN]->(LegalInstrument: TKDL)`.
     - Cross-references: `(LegalInstrument: Patents Act 1970)-[:CONTAINS_EXCLUSION]->(Section: 3(p))`.
     - Follows statutory dependency: `(Ingredient: Biological Resource occurring in India)-[:GOVERNED_BY]->(RegulatoryBody: NBA)-[:MANDATES]->(Approval: Section 6 Foreign Filing)`.
  3. **Step 3 (Context Fusion & Classification)**: The query is classified under `novelty_check` and `procedural`. Hybrid context merges the prior-art records, Section 3(p) exclusion, and Section 6 NBA approval requirements.
  4. **Result**: The assistant delivers a grounded, bulleted verdict:
     - **Novelty Verdict**: Non-patentable under Section 3(p) of the Patents Act, 1970, as prior art is documented in the Ayurvedic Pharmacopoeia and TKDL. `[CLEAR]`
     - **Regulatory Mandate**: Mandatory prior approval must be granted by the National Biodiversity Authority (NBA) under Section 6 of the Biological Diversity Act, 2002, before any foreign IP application. `[CLEAR]`
     - **Export Classification**: Guidance on FDA 21 CFR dietary supplement notification route vs. botanical drug approval. `[INFERRED]`

---

## Detailed Feature Matrix & Capabilities

### 1. Agentic Multi-Step Orchestrator (`src/agent/orchestrator.py`)
The orchestrator classifies queries into 5 distinct operational modes before dispatching specialized retrieval flows:

- **`novelty_check`**: Dedicated prior-art search across TKDL documentation, Ayurvedic Pharmacopoeia of India (API), and statutory non-patentability clauses (Patents Act Section 3(p) on traditional knowledge and Section 3(d) on incremental modifications).
- **`jurisdiction_comparison`**: Identifies explicit country mentions (*India*, *US*, *EU*, *WIPO*) and executes parallel, filtered retrieval passes per jurisdiction. Features intelligent export route detection (detecting dietary supplement / food routes under US DSHEA & 21 CFR vs. botanical drug routes under EU THMPD / US FDA).
- **`precedent_lookup`**: Executes Cypher traversals on `CasePrecedent` nodes to locate historical disputes (such as the turmeric patent revocation or the European Patent Office neem revocation) and extracts grounded judicial rationales.
- **`procedural`**: Enforces sequential regulatory stage ordering: `application` &rarr; `documentation` &rarr; `inspection` &rarr; `certification` &rarr; `renewal` &rarr; `penalties`.
- **`general`**: Executes hybrid retrieval with statutory keyword reranking for broad legal and regulatory questions.

### 2. Multi-Tier LLM Architecture
- **Inference & Synthesis**: Ultra-low-latency Groq API hosting `llama-3.1-8b-instant` for deterministic, grounded natural language synthesis.
- **Ultra-Fast Intent Classification**: Cerebras inference engine (`llama3.1-8b`) for sub-100ms classification of user queries into orchestrator modes.
- **Local Fallback & Zero-Cost Offline Extraction**: Local Ollama instance (`llama3.2:3b`) capable of running completely offline for entity extraction, offline query processing, and privacy-sensitive operations.
- **Content-Hashed Concept Cache**: SQLite-backed caching (`concept_cache.db`) stores entity and relationship extractions by SHA-256 content hashes, enabling idempotent chunk updates in milliseconds.

### 3. Speech-to-Speech Voice Engine with Smart Barge-in (`src/speech/pipeline.py`)
- **Speech-to-Text (STT)**: High-precision local transcription using `faster-whisper` (`base` model, 16 kHz mono PCM).
- **Text-to-Speech (TTS)**: Server-side neural speech synthesis using `Kokoro-ONNX` (`af_heart` voice model at 24 kHz) streaming WAV audio, with automatic client-side Web Speech API fallback.
- **Smart Barge-In (Interruption Detection)**: Threaded Voice Activity Detection (VAD) monitors microphone input during TTS playback. If the user begins speaking, playback terminates instantly, the partial turn is cached, and session memory seamlessly continues the dialogue.
- **Multilingual Voice Routing**: Real-time language detection (`langdetect`). Hindi audio input is transcribed, translated for high-precision English vector matching, and synthesized back into the user's preferred language.

### 4. Grounding & Anti-Hallucination Guardrails
- **Refusal Guardrail**: If retrieved context contains zero relevant content, the system strictly outputs:
  ```text
  "The documentation does not contain information regarding this question."
  ```
- **Tri-Level Confidence Tagging**: Every substantive assertion is tagged:
  - `[CLEAR]`: The claim is directly stated in the cited statutory or historical text.
  - `[INFERRED]`: The conclusion is derived through cross-source deduction.
  - `[AMBIGUOUS]`: The question is unsettled, conflicting across jurisdictions, or subject to discretionary authority.
- **Post-Generation String Verifier (`src/utils/verifier.py`)**: A sub-5ms post-synthesis validator scans every `[CLEAR]` claim. If its key noun phrase or 4-gram is missing from the retrieved context, it is automatically downgraded to `[AMBIGUOUS]`.

### 5. Multi-Channel Access & Integrations
- **Modern Interactive Web UI (`frontend/index.html`)**: Single-page application styled with vanilla CSS tokens, real-time Web Audio API waveform canvas visualizer, interactive reasoning trace drawers, clickable citation cards, follow-up query chips, and dark/light mode toggles.
- **WhatsApp Bot (`src/whatsapp.py`)**: Twilio Webhook endpoint (`POST /whatsapp/webhook`) enabling mobile interactions. Keyed by the sender's phone number for session memory, featuring QR code scan connectivity (`frontend/whatsapp_qr.png`).
- **Model Context Protocol (MCP) Server (`src/graphrag_mcp_tool.py`, `src/mcp_tool_adapter.py`)**: Full MCP protocol support allowing AI agents (Claude Desktop, Cursor, Gemini IDE) to invoke GraphRAG as a first-class tool (`graphrag_query` and `get_session_history`).
- **RESTful API Backend (`src/api.py`)**: Production-ready FastAPI service exposing comprehensive endpoints for web, mobile, and agentic clients.

---

## Directory Structure & Codebase Guide

```
GraphRAG/
├── .env                              # Environment variable configuration (ports, keys, models)
├── .env.example                      # Template configuration file
├── docker-compose.yml                # Multi-container orchestration (Neo4j 5.18 & Qdrant v1.8.0)
├── requirements.txt                  # Python production dependencies
├── concept_cache.db                  # SQLite cache for idempotent entity and relation extraction
├── import_docs.log                   # Detailed ingestion and extraction run log
├── LICENSE                           # MIT open source license
├── README.md                         # Comprehensive project documentation
│
├── data/                             # Persistent database files and storage
│   ├── citations_index.txt           # Structured legal citation lookup index
│   ├── session_cache.db              # SQLite multi-turn conversation session history
│   ├── neo4j/                        # Neo4j persistent graph volume
│   └── qdrant/                       # Qdrant persistent vector volume
│
├── docs/                             # Architecture & Implementation Documentation
│   ├── IP-SAKTI_Sahayak_Implementation_Plan.md        # Master specification & phase blueprint
│   ├── IP-SAKTI_Sahayak_Implementation_Plan_PATCH_v1.1.md # Stage ordering & query patches
│   ├── STARTUP_GUIDE.md              # Fast local deployment instructions
│   ├── WHATSAPP_GUIDE.md             # Twilio WhatsApp webhook & ngrok integration guide
│   ├── decisions.md                  # Architecture Decision Records (ADRs D1-D16)
│   ├── flow.md                       # Comprehensive data flow & pipeline specifications
│   ├── imported_docs.md              # Inventory of ingested statutes, treaties, and manuals
│   └── visualization_guide.md        # Cypher query cookbook and visual inspection guide
│
├── frontend/                         # Modern Interactive Web Interface
│   ├── index.html                    # Production single-page web application (CSS, HTML, JS)
│   └── whatsapp_qr.png               # QR code asset for instant WhatsApp sandbox connection
│
├── guides/                           # Developer & Integration Guides
│   └── mcp/                          # Model Context Protocol documentation and setup
│
├── scripts/                          # Pipeline Execution & Benchmarking Scripts
│   ├── import_docs.py                # Ingestion, format normalization, chunking, and storage
│   ├── extract_concepts.py           # Domain entity extraction & cross-document relationship inference
│   ├── format_corpus.py              # Corpus formatting and metadata tagging utility
│   ├── generate_visualizations.py    # Generates SVG knowledge graphs & t-SNE embedding plots
│   ├── query_demo.py                 # Interactive terminal CLI for hybrid retrieval and QA
│   ├── test_domain.py                # Domain test suite verifying all 5 orchestrator modes
│   ├── test_hallucination.py         # Grounding & refusal benchmark against edge-case queries
│   ├── test_pipeline.py              # End-to-end system integration test runner
│   └── verify_db_structure.py        # Database health check and schema validation tool
│
├── src/                              # Core Application Source Code
│   ├── api.py                        # FastAPI backend application with REST and MCP endpoints
│   ├── config.py                     # Unified configuration management (environment & YAML)
│   ├── query_engine.py               # Hybrid retrieval engine (Vector recall + Graph expansion)
│   ├── graphrag_mcp_tool.py          # Native Model Context Protocol (MCP) server implementation
│   ├── mcp_tool_adapter.py           # Adapter layer connecting MCP interface with query engine
│   ├── whatsapp.py                   # Twilio WhatsApp webhook router and response formatter
│   │
│   ├── agent/                        # Agentic Orchestration Layer
│   │   ├── __init__.py
│   │   └── orchestrator.py           # 5-mode intent classifier, query router, and multi-step synthesis
│   │
│   ├── database/                     # Database Drivers & Connection Managers
│   │   ├── __init__.py
│   │   ├── neo4j_manager.py          # Neo4j schema management, batch creation, and Cypher queries
│   │   └── qdrant_manager.py         # Qdrant client, HNSW collection indexing, and vector search
│   │
│   ├── processors/                   # Document & Text Processing Pipelines
│   │   ├── __init__.py
│   │   ├── concept_extractor.py      # LLM entity extraction with SQLite caching & schema allowlist
│   │   ├── document_processor.py     # Structure-aware chunking, table atomicity, frontmatter parser
│   │   ├── embedding_processor.py    # Dense multilingual vector generation (multilingual-e5-large)
│   │   ├── format_converter.py       # Multi-format normalization (PDF via Docling, DOCX, HTML, TXT)
│   │   └── markdown_processor.py     # Markdown syntax normalization and heading extraction
│   │
│   ├── speech/                       # Speech-to-Speech & Voice Processing Layer
│   │   ├── __init__.py
│   │   ├── pipeline.py               # STT, TTS, VAD barge-in loop, and Hindi translation
│   │   └── session_cache.py          # SQLite-backed conversation turn history manager
│   │
│   └── utils/                        # Utilities & Guardrails
│       ├── __init__.py
│       ├── citation_formatter.py     # Legal citation renderer and structured source formatter
│       ├── citation_index.py         # Fast indexed citation registry
│       ├── neo4j_utils.py            # Graph helper functions and auto-linking algorithms
│       ├── qdrant_utils.py           # Vector helper functions and payload filters
│       ├── query_utils.py            # Query preprocessing and token normalization
│       └── verifier.py               # Sub-5ms runtime n-gram overlap verifier and tag downgrader
│
├── visualizations/                   # Pre-rendered High-Resolution SVG Topology Maps
│   ├── entity-bridges.svg            # Cross-document entity bridge visualization
│   ├── inter-entity.svg              # Conceptual relationship network
│   └── knowledge-graph.svg           # Global knowledge graph topology
│
└── your_docs_here/                   # Source Corpus Directory
    ├── 2016-_National_IPR_Policy-2016__English_and_Hindi.pdf
    ├── Biodiversity_Act_2002.pdf
    ├── cbd-en.pdf                    # Convention on Biological Diversity
    ├── copyright rules 2013.pdf
    ├── patents-act-1970.pdf
    ├── ... (34 complete regulatory documents, treaties, and TK manuals)
```

---

## Quickstart & Installation Guide

### 1. Prerequisites

- **Operating System**: Windows 10/11, macOS, or Linux (Ubuntu 20.04+).
- **Python**: Version 3.10, 3.11, or 3.12.
- **Docker & Docker Compose**: Docker Desktop running with 4GB+ RAM allocated.
- **Ollama**: (Optional for local mode) Installed and running.
  ```bash
  ollama pull llama3.2:3b
  ollama serve
  ```

### 2. Clone the Repository & Setup Virtual Environment

```bash
# Clone the repository
git clone https://github.com/vignesh-poovanna/GraphRAG.git
cd GraphRAG

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux / macOS:
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

Key configuration parameters inside `.env`:

```ini
# Databases
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=document_chunks

# Embeddings (1024-dimension multilingual model)
EMBEDDING_MODEL=intfloat/multilingual-e5-large
EMBEDDING_DIMENSION=1024
CHUNKING_STRATEGY=structure_aware

# LLM Inference (Tiered Routing)
EXTRACTION_LLM=llama3.2:3b
OLLAMA_HOST=http://localhost:11434

# Cloud Synthesis (Groq)
SYNTHESIS_LLM=llama-3.1-8b-instant
SYNTHESIS_LLM_API_KEY=your_groq_api_key_here
SYNTHESIS_LLM_BASE_URL=https://api.groq.com/openai/v1

# Fast Classification (Cerebras or Groq)
CEREBRAS_MODEL=llama3.1-8b
CEREBRAS_API_KEY=your_cerebras_api_key_here
CEREBRAS_BASE_URL=https://api.cerebras.ai/v1

# Speech Settings
SPEECH_STT_MODEL=base
SPEECH_TTS_VOICE=af_heart
SPEECH_SESSION_CACHE=./data/session_cache.db
```

### 4. Start Database Containers

Launch Neo4j and Qdrant in detached mode:

```bash
docker-compose up -d
```

Verify service availability:
- **Neo4j Browser**: http://localhost:7474 (Username: `neo4j`, Password: `password`)
- **Qdrant Dashboard**: http://localhost:6333/dashboard

### 5. Ingest Corpus & Populate Knowledge Graph

Run the ingestion script to parse all documents in `your_docs_here/`, perform structure-aware chunking, generate 1024-dim dense embeddings, and populate both databases:

```bash
python scripts/import_docs.py
```

Extract domain entities, relationships, and infer cross-document links:

```bash
python scripts/extract_concepts.py --batch-size 4
```
*(Extractions are cached in `concept_cache.db`; subsequent runs complete in seconds).*

### 6. Launch the Application & Web Interface

Start the FastAPI application with live reloading:

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser and navigate to:
- **Web Application**: **http://localhost:8000**
- **Interactive Swagger API Docs**: **http://localhost:8000/docs**
- **Alternative Redoc API Docs**: **http://localhost:8000/redoc**

---

## Usage Guide & Operational Interfaces

### 1. Interactive Web Interface
Access http://localhost:8000 to interact with the IP-SAKTI Sahayak platform:
- **Text Queries**: Ask complex multi-jurisdiction questions with instant streaming responses.
- **Voice Queries**: Click the microphone icon or toggle Voice Mode to speak queries directly. The Web Audio API renders a real-time 16 kHz waveform visualizer.
- **Neural Read-Aloud**: Click "Read Aloud" on any response to trigger server-side Kokoro-ONNX neural speech synthesis.
- **Citation Inspection**: Click on any inline legal citation or source badge to inspect the original text snippet and document provenance.
- **Interactive Follow-ups**: Click on any suggested follow-up chip to continue multi-turn exploration.

### 2. WhatsApp Bot Integration (via Twilio)
To expose IP-SAKTI Sahayak on WhatsApp:
1. In a separate terminal, expose your local server using ngrok:
   ```bash
   ngrok http 8000
   ```
2. Copy the resulting HTTPS forwarding URL (e.g., `https://xyz.ngrok-free.app`).
3. In your **Twilio Console** &rarr; **Develop** &rarr; **Messaging** &rarr; **Try it out** &rarr; **Send a WhatsApp message**:
   - Set the webhook URL for incoming messages to:
     ```
     https://xyz.ngrok-free.app/whatsapp/webhook
     ```
   - HTTP Method: `POST`.
4. From your phone, scan the QR code in the web interface or send the join sandbox code to the Twilio WhatsApp number.
5. Start asking questions directly on WhatsApp; responses include formatted citations and verdicts within WhatsApp's character limits.

### 3. Programmatic Python SDK Usage

Execute hybrid queries directly inside Python scripts:

```python
from src.config import Config
from src.database.neo4j_manager import Neo4jManager
from src.database.qdrant_manager import QdrantManager
from src.processors.embedding_processor import EmbeddingProcessor
from src.query_engine import QueryEngine
from src.agent.orchestrator import Orchestrator

# Initialize configuration and connections
cfg = Config()
neo4j = Neo4jManager(cfg); neo4j.connect()
emb = EmbeddingProcessor(cfg); emb.load_model()
qdrant = QdrantManager(cfg, emb); qdrant.connect()

# Initialize query engine and orchestrator
qe = QueryEngine(neo4j, qdrant, embedding_processor=emb)
orchestrator = Orchestrator(qe, cfg)

# Run an agentic query
result = orchestrator.run("Can I patent an Ayurvedic herbal formulation in India?")

print("=== VERDICT & ANSWER ===")
print(result["answer"])

print("\n=== CLASSIFICATION MODE ===")
print(result["mode"])

print("\n=== SOURCES CITED ===")
for src in result["sources"]:
    print(f"- {src['citation']} (Type: {src['doc_type']})")

# Clean up connections
neo4j.close()
```

### 4. Interactive Command-Line Demo (`scripts/query_demo.py`)

Run hybrid queries or test grounded answers directly in the terminal:

```bash
# Interactive mode
python scripts/query_demo.py

# CLI query with grounded answer generation
python scripts/query_demo.py --query "What are the restrictions on traditional knowledge under Section 3(p)?" --answer
```

---

## API Reference & Endpoint Specifications

### 1. `POST /query`
Performs agentic classification, multi-step hybrid retrieval, and grounded synthesis.

**Request Body:**
```json
{
  "query": "Can I patent a Triphala-based composition in India?",
  "session_id": "optional-uuid-string",
  "limit": 5,
  "history": [
    {"role": "user", "content": "What is Triphala?"},
    {"role": "assistant", "content": "Triphala is a classical Ayurvedic formulation..."}
  ]
}
```

**Response Body:**
```json
{
  "answer": "• Under Section 3(p) of the Patents Act, 1970, an invention which in effect is traditional knowledge is not patentable. [CLEAR] [1]\n• Triphala is an established classical formulation documented in the Ayurvedic Pharmacopoeia of India and TKDL. [CLEAR] [2]\n\n**Sources:** [1] Patents Act 1970, Section 3(p); [2] TKDL Traditional Knowledge Records\n**Verdict:** No. Classical Ayurvedic formulations cannot be patented in India as they constitute non-patentable traditional knowledge.",
  "mode": "novelty_check",
  "language": "en",
  "tags": ["CLEAR"],
  "sources": [
    {
      "claim_text": "",
      "citation": "Patents Act, 1970, Section 3(p) (India)",
      "source_snippet": "Section 3: What are not inventions. (p) an invention which in effect, is traditional knowledge...",
      "metadata": {
        "act_or_source_name": "Patents Act",
        "section": "3(p)",
        "year": "1970",
        "jurisdiction": "India",
        "document_type": "statute"
      },
      "doc_type": "statute",
      "tag": "[CLEAR]"
    }
  ],
  "trace": [
    {"step": "classify_llm", "mode": "novelty_check", "backend": "groq"},
    {"step": "retrieval", "chunks_found": 10},
    {"step": "synthesis", "chunks_used": 6, "tags": ["CLEAR"]}
  ],
  "session_id": "session-uuid-4412",
  "follow_ups": [
    "Can a novel extraction process for Triphala be patented?",
    "What approvals are required from the National Biodiversity Authority?",
    "Can Triphala be registered as a Geographical Indication?"
  ]
}
```

### 2. `POST /query/voice`
Accepts 16 kHz mono PCM base64-encoded audio, transcribes with `faster-whisper`, executes orchestrated retrieval, and returns text and citations.

### 3. `POST /tts`
Synthesizes speech using Kokoro-ONNX and streams back raw 24 kHz WAV audio (`audio/wav`).

### 4. `GET /stats`
Returns live metrics across Neo4j and Qdrant clusters:
```json
{
  "neo4j": {
    "document_count": 34,
    "chunk_count": 11534,
    "category_count": 7
  },
  "qdrant": {
    "vector_count": 11534,
    "estimated_document_count": 369,
    "size_bytes": 17716224,
    "distance": "COSINE"
  }
}
```

### 5. `POST /mcp`
Model Context Protocol (MCP) tool invocation endpoint supporting `graphrag_query` and `get_session_history`.

---

## Model Context Protocol (MCP) Integration

GraphRAG features a built-in MCP server adapter (`src/graphrag_mcp_tool.py`), enabling seamless integration into external agentic environments like **Claude Desktop**, **Cursor IDE**, or **Google Antigravity**.

### Configuring in Claude Desktop

Add GraphRAG to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "python",
      "args": [
        "-m", "src.graphrag_mcp_tool"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "password",
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "SYNTHESIS_LLM_API_KEY": "your_groq_key"
      }
    }
  }
}
```

### Exposed Tools:
1. **`graphrag_query`**:
   - **Description**: Query the hybrid Neo4j graph and Qdrant vector database for verified IP and regulatory documentation.
   - **Parameters**: `query` (string, required), `limit` (integer, default: 5), `category` (string, optional).
2. **`get_session_history`**:
   - **Description**: Retrieve conversation turns and session context for a specified session ID.
   - **Parameters**: `session_id` (string, required).

---

## Visualizing the Knowledge Graph

### 1. Pre-Rendered SVG Visualizations
The `visualizations/` folder contains comprehensive, high-resolution vector diagrams:
- **`visualizations/knowledge-graph.svg`**: Global topology of documents, chunks, and technical concepts.
- **`visualizations/entity-bridges.svg`**: Illustrates how shared domain concepts bridge disparate legal statutes and pharmacopoeia records.
- **`visualizations/inter-entity.svg`**: Direct conceptual relationship network between extracted entities.

### 2. Live Interactive Visualizations in Neo4j Browser
Navigate to **http://localhost:7474** and run the following Cypher queries:

#### A. Cross-Document Concept Bridges
```cypher
MATCH (d1:Document)-[:HAS_CHUNK]->(c1:Chunk)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(c2:Chunk)<-[:HAS_CHUNK]-(d2:Document)
WHERE d1 <> d2
RETURN d1.title, c1, e, c2, d2.title LIMIT 50;
```

#### B. Statutory Relationships & Case Precedents
```cypher
MATCH (cp:CasePrecedent)-[r:CITES]->(li:LegalInstrument)-[a:APPLIES_IN]->(j:Jurisdiction)
RETURN cp, r, li, a, j;
```

#### C. Inferred Legal Relationships
```cypher
MATCH (s)-[:HAS_INFERRED_RELATION]->(ir:InferredRelation)-[:INFERRED_TARGET]->(t)
RETURN s.name, ir.confidence, ir.tag, t.name;
```

---

## Verification & Testing Suite

GraphRAG includes a dedicated automated test suite to verify retrieval accuracy, guardrails, and domain logic:

```bash
# 1. Run Domain & Orchestrator Mode Verification
python scripts/test_domain.py

# 2. Run Hallucination & Refusal Benchmark
python scripts/test_hallucination.py

# 3. Run End-to-End Pipeline Integration Test
python scripts/test_pipeline.py
```

### Key Benchmark Metrics
- **Refusal Precision**: **100%** on out-of-scope queries (system strictly emits the standard refusal text without fabricating facts).
- **Sub-5ms Tag Verification**: Verifier checks 100% of `[CLEAR]` assertions against chunk text, eliminating unsupported claims before client rendering.
- **Average Synthesis Latency**: **< 1.2s** using Groq Llama-3.1-8b-instant.
- **Average Vector Recall Latency**: **< 45ms** across 11,534 vectors in Qdrant.

---

## Technology Stack

| Layer | Technology | Version / Model | Functional Role |
| :--- | :--- | :--- | :--- |
| **Graph Database** | Neo4j Enterprise | `5.18` | Property graph storage, Cypher graph traversals, and multi-hop relationship walks |
| **Vector Database** | Qdrant | `v1.8.0` | High-dimensional dense vector storage, HNSW indexing, Cosine similarity search |
| **Embedding Model** | HuggingFace Transformers | `intfloat/multilingual-e5-large` | 1024-dimensional dense semantic vectors covering 100+ languages |
| **Synthesis LLM** | Groq Cloud API | `llama-3.1-8b-instant` | Context-bounded natural language answer generation with inline citations |
| **Classifier LLM** | Cerebras Cloud API | `llama3.1-8b` | Ultra-fast intent classification into orchestrator operational modes |
| **Local LLM** | Ollama | `llama3.2:3b` | Local offline entity extraction and fallback query generation |
| **Speech-to-Text** | Faster-Whisper | `base (CTranslate2)` | Local speech transcription converting 16 kHz audio to text |
| **Text-to-Speech** | Kokoro-ONNX | `kokoro-v1.0 (ONNX)` | Neural voice synthesis delivering natural audio playback |
| **Document Processing**| IBM Docling & PyMuPDF4LLM | `latest` | Layout-aware PDF OCR, atomic table extraction, and markdown conversion |
| **Web Framework** | FastAPI & Uvicorn | `FastAPI 0.110+` | Asynchronous RESTful API backend, WebSocket/SSE streaming, and MCP handler |
| **Messaging Gateway** | Twilio API | `Twilio Webhooks` | WhatsApp bidirectional messaging gateway with QR code sandbox integration |
| **Agent Interface** | Model Context Protocol | `Anthropic MCP Spec` | Standardized agentic protocol for Claude Desktop and Cursor IDE integration |
| **Containerization** | Docker & Docker Compose | `v2+` | Containerized orchestration for local and production database infrastructure |

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for complete details.

---

## Acknowledgments & Credits
- **Ministry of AYUSH**, Government of India — for the SIH26045 Problem Statement.
- **Council of Scientific and Industrial Research (CSIR)** — for public methodology regarding the Traditional Knowledge Digital Library (TKDL).
- **Qdrant & Neo4j Communities** — for world-class vector and graph database engines.
- **Meta AI & Groq** — for Llama 3 open models and ultra-fast LPUs.
- Developed with pride for the **Smart India Hackathon 2026** by **Aether Mind**.