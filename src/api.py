"""
api.py — Phase 9 FastAPI backend

Wraps the orchestrator and speech pipeline behind a REST API.
Also exposes MCP-compatible tool endpoints (thin wrapper over the same core).

Endpoints:
  POST /query          — text query → orchestrated answer + sources + trace
  POST /query/voice    — base64-encoded audio → same response shape
  GET  /sessions/{id}  — retrieve session history from SQLite
  GET  /stats          — database statistics
  GET  /health         — liveness check

CORS is enabled for localhost:3000 (React dev server).
Run:
  uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
"""

import base64
import io
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import Config
from src.database.neo4j_manager import Neo4jManager
from src.database.qdrant_manager import QdrantManager
from src.processors.embedding_processor import EmbeddingProcessor
from src.query_engine import QueryEngine
from src.agent.orchestrator import Orchestrator
from src.speech.session_cache import SessionCache
from src.utils.citation_index import load_citations_index

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise heavy objects once at startup."""
    cfg = Config()
    load_citations_index("./data/citations_index.txt")

    neo4j = Neo4jManager(cfg)
    neo4j.connect()

    embedding = EmbeddingProcessor(cfg)
    embedding.load_model()

    qdrant = QdrantManager(cfg, embedding_model=embedding)
    qdrant.connect()

    qe = QueryEngine(neo4j, qdrant, embedding_processor=embedding)
    orch = Orchestrator(qe, cfg)
    cache = SessionCache(cfg.get("speech.session_cache", "./data/session_cache.db"))

    _state.update({"cfg": cfg, "qe": qe, "orch": orch, "cache": cache})
    logger.info("API ready")
    yield

    neo4j.close()


app = FastAPI(
    title="IP-SAKTI Sahayak API",
    description="Multilingual Agentic RAG for Ayurveda IP & Regulatory Guidance",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    limit: int = 5


class VoiceQueryRequest(BaseModel):
    audio_b64: str          # base64-encoded WAV/MP3 bytes
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    mode: str
    language: str
    tags: list[str]
    sources: list[dict]
    trace: list[dict]
    session_id: str


# ---------------------------------------------------------------------------
# Text query
# ---------------------------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    Main query endpoint.
    The orchestrator classifies, retrieves multi-step, and synthesises.
    """
    orch: Orchestrator = _state["orch"]
    cache: SessionCache = _state["cache"]

    sid = cache.new_session(req.session_id)
    history = cache.get_history(sid, last_n=4)

    # Language detection + translation handled inside pipeline.query()
    # but here we call orchestrator directly (voice pipeline handles its own)
    from src.speech.pipeline import SpeechPipeline
    pipe = SpeechPipeline(orch, _state["cfg"], session_id=sid)
    result = pipe.query(req.query)

    return QueryResponse(
        answer=result.get("answer", ""),
        mode=result.get("mode", "general"),
        language=result.get("language", "en"),
        tags=result.get("tags", []),
        sources=result.get("sources", []),
        trace=result.get("trace", []),
        session_id=sid,
    )


# ---------------------------------------------------------------------------
# Voice query
# ---------------------------------------------------------------------------

@app.post("/query/voice", response_model=QueryResponse)
async def query_voice(req: VoiceQueryRequest):
    """
    Accepts base64-encoded audio, transcribes via faster-whisper,
    routes through orchestrator, returns text response.
    (TTS playback is handled client-side — the API returns text only.)
    """
    import soundfile as sf
    from src.speech.pipeline import SpeechPipeline

    orch: Orchestrator = _state["orch"]
    cfg = _state["cfg"]
    cache: SessionCache = _state["cache"]
    sid = cache.new_session(req.session_id)

    try:
        audio_bytes = base64.b64decode(req.audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        audio, sr = sf.read(tmp_path)
        os.unlink(tmp_path)

        # Resample to 16 kHz if needed
        if sr != 16000:
            try:
                import librosa
                audio = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=16000)
            except ImportError:
                pass   # best-effort; whisper handles non-16k too

        pipe = SpeechPipeline(orch, cfg, session_id=sid)
        pipe._load_stt()
        text = pipe._transcribe(audio.astype(np.float32))
        if not text:
            raise HTTPException(status_code=422, detail="Could not transcribe audio")

        result = pipe.query(text)
        return QueryResponse(
            answer=result.get("answer", ""),
            mode=result.get("mode", "general"),
            language=result.get("language", "en"),
            tags=result.get("tags", []),
            sources=result.get("sources", []),
            trace=result.get("trace", []),
            session_id=sid,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Voice query error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------

@app.get("/sessions/{session_id}")
async def get_session(session_id: str, last_n: int = 20):
    """Retrieve the last N turns for a session."""
    cache: SessionCache = _state["cache"]
    history = cache.get_history(session_id, last_n=last_n)
    return {"session_id": session_id, "history": history, "turn_count": len(history)}


@app.get("/sessions")
async def list_sessions(limit: int = 20):
    """List recent sessions."""
    cache: SessionCache = _state["cache"]
    return {"sessions": cache.list_sessions(limit=limit)}


# ---------------------------------------------------------------------------
# Stats + health
# ---------------------------------------------------------------------------

@app.get("/stats")
async def stats():
    qe: QueryEngine = _state["qe"]
    return qe.get_statistics()


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}


# ---------------------------------------------------------------------------
# MCP-compatible tool interface (same core, JSON-RPC envelope)
# ---------------------------------------------------------------------------

class MCPRequest(BaseModel):
    tool: str
    arguments: dict


@app.post("/mcp")
async def mcp_call(req: MCPRequest):
    """
    MCP tool interface — wraps the same orchestrator as /query.
    Supported tools: graphrag_query, get_session_history
    """
    if req.tool == "graphrag_query":
        query_text = req.arguments.get("query", "")
        session_id = req.arguments.get("session_id")
        result = await query(QueryRequest(query=query_text, session_id=session_id))
        return {"result": result.model_dump()}
    elif req.tool == "get_session_history":
        sid = req.arguments.get("session_id", "")
        data = await get_session(sid)
        return {"result": data}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {req.tool}")
