"""
whatsapp.py — Phase 10 (IP-SAKTI Sahayak)

Twilio WhatsApp webhook.  Mounts at /whatsapp/webhook.

Flow:
  WhatsApp message → Twilio → POST /whatsapp/webhook
  → run RAG pipeline async (up to 13 s) → TwiML reply

The Twilio sandbox only accepts freeform text via TwiML webhook
responses — the outbound REST API requires ContentSid templates.
We beat the 15 s timeout by running the pipeline in a thread executor
and waiting up to 13 s before returning TwiML.
"""

import asyncio
import logging
import os
import re

from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

_WA_LIMIT   = 1600
_TIMEOUT_S  = 14   # Twilio kills webhook at 15 s; leave 1 s buffer


def _twiml(text: str) -> str:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'


def _strip_markdown(text: str) -> str:
    """Clean for WhatsApp — remove HTML/raw doc IDs, keep *bold* and - bullets."""
    text = re.sub(r'##\s*Citations[\s\S]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'FOLLOW_UPS:.*', '', text)
    text = re.sub(r'<[^>]+>', '', text)                   # HTML tags
    text = re.sub(r'\[CLEAR\]|\[AMBIGUOUS\]|\[INFERRED\]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def _clean_chunk(text: str) -> str:
    """Strip markdown table syntax and pipe chars from RAG chunk text."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r'^\|[-|\s]+\|$', line):  # separator row |---|---|
            continue
        line = re.sub(r'\|', ' ', line)        # pipe → space
        line = re.sub(r'\*+', '', line)        # strip bold/italic asterisks
        line = re.sub(r'\s{2,}', ' ', line)   # collapse whitespace
        if line:
            lines.append(line)
    return ' '.join(lines).strip()


def _run_pipeline(app_state: dict, text: str, session_id: str) -> str:
    """
    Fast WhatsApp path: Qdrant-only search (~0.3s) + allam-2-7b (~1.3s).
    Formatting done in Python — not by the LLM — for reliability.
    """
    import os
    from openai import OpenAI

    qe  = app_state["orch"].qe
    cfg = app_state["cfg"]

    api_key  = cfg.get("llm.synthesis_api_key",  "") or os.getenv("SYNTHESIS_LLM_API_KEY", "")
    base_url = cfg.get("llm.synthesis_base_url", "https://api.groq.com/openai/v1")

    if not api_key:
        return "API not configured. Please contact support."

    # Qdrant-only (no Neo4j) — fast
    chunks = qe.semantic_search(text, limit=4)
    if not chunks:
        return "I could not find relevant information for your query."

    # Build context and source labels
    # Payload fields are FLAT on each chunk dict (not nested under 'metadata').
    # The document title comes from chunk['document']['title'] (added by semantic_search).
    ctx_parts  = []
    src_labels = []
    for i, c in enumerate(chunks, 1):
        doc   = c.get("document") or {}
        label = (
            c.get("act_or_source_name")
            or c.get("title")
            or doc.get("title")
            or doc.get("name")
            or (os.path.splitext(os.path.basename(c.get("path", "")))[0] if c.get("path") else None)
            or c.get("doc_id", f"Source {i}")
        )
        ctx_parts.append(f"[{i}] {_clean_chunk(c.get('text', ''))[:350]}")
        src_labels.append(f"[{i}] {label}")

    context = "\n".join(ctx_parts)

    # Ask model for plain numbered content — we format it below
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=cfg.get("llm.synthesis_model", "qwen/qwen3.8-27b"),
        messages=[
            {"role": "system", "content": (
                "You are an Indian IP law assistant for Ayurveda and traditional knowledge.\n"
                "Use ONLY the numbered excerpts. Do NOT copy excerpt text verbatim.\n\n"
                "Reply with plain text:\n"
                "Line 1: One sentence verdict starting with Yes, No, or Conditional.\n"
                "Lines 2-5: Numbered points, each naming a specific Act/Section, "
                "one sentence explanation, ending with [N] for the excerpt used."
            )},
            {"role": "user", "content": f"Excerpts:\n{context}\n\nQuestion: {text}"},
        ],
        temperature=0.0,
        max_tokens=300,
        extra_body={"reasoning_effort": "none"},
    )
    raw = resp.choices[0].message.content.strip()

    # ── Python-side WhatsApp formatting ─────────────────────────────────────
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    summary = re.sub(r'^(summary:?\s*|1\.\s*)', '', lines[0] if lines else "", flags=re.IGNORECASE).strip()

    bullets = []
    for l in lines[1:]:
        l = re.sub(r'^[\d]+[.)]\s*', '', l)   # strip "1. "
        l = re.sub(r'^[-•]\s*', '', l)         # strip "- "
        if l:
            bullets.append(f"- {l}")

    src_block = "\n".join(src_labels)
    parts = [f"*Summary:* {summary}"]
    if bullets:
        parts.append("\n".join(bullets))
    parts.append(f"*Sources:*\n{src_block}")
    return "\n\n".join(parts)


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
):
    text   = Body.strip()
    sender = From.strip()

    if not text or not sender:
        return PlainTextResponse(_twiml("No message received."), media_type="application/xml")

    logger.info("WhatsApp [%s]: %s", sender, text[:80])

    session_id = f"wa_{sender.replace(':', '_').replace('+', '')}"
    app_state  = request.app.state.sakti

    loop = asyncio.get_event_loop()
    try:
        answer = await asyncio.wait_for(
            loop.run_in_executor(None, _run_pipeline, app_state, text, session_id),
            timeout=_TIMEOUT_S,
        )
        answer = _strip_markdown(answer)
    except asyncio.TimeoutError:
        logger.warning("WhatsApp pipeline timed out for %s", sender)
        answer = (
            "⏳ Your question is taking longer than usual to process.\n"
            "Please resend your message in a few seconds and you'll get the full answer."
        )
    except Exception as e:
        logger.error("WhatsApp query error: %s", e)
        answer = "⚠️ Something went wrong. Please try again."

    if len(answer) > _WA_LIMIT:
        answer = answer[:_WA_LIMIT - 20] + "\n\n[…reply truncated]"

    return PlainTextResponse(_twiml(answer), media_type="application/xml")
