"""
whatsapp.py — Phase 10 (IP-SAKTI Sahayak)

Twilio WhatsApp webhook.  Mounts at /whatsapp/webhook.

Flow:
  WhatsApp message → Twilio → POST /whatsapp/webhook
  → SpeechPipeline.query() → TwiML text reply → WhatsApp

Session memory: keyed by the sender's WhatsApp number so each user
gets their own persistent conversation history.
"""

import logging
import os

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Max chars WhatsApp allows in one message
_WA_LIMIT = 1600


def _twiml_reply(text: str) -> str:
    """Wrap text in a minimal TwiML response."""
    # Escape XML special chars
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
):
    """
    Twilio posts form-encoded data here.
    We pull the message body + sender number, run the query, reply with TwiML.
    """
    # _state is populated by api.py lifespan; access via app.state
    app_state = request.app.state.sakti

    text = Body.strip()
    sender = From.strip()   # e.g. "whatsapp:+919876543210"

    if not text or not sender:
        return PlainTextResponse(_twiml_reply("No message received."), media_type="application/xml")

    logger.info("WhatsApp [%s]: %s", sender, text[:80])

    # Use sender number as stable session_id (persistent per user)
    session_id = f"wa_{sender.replace(':', '_').replace('+', '')}"

    try:
        from src.speech.pipeline import SpeechPipeline
        pipe = SpeechPipeline(app_state["orch"], app_state["cfg"], session_id=session_id)
        result = pipe.query(text)
        answer = result.get("answer", "Sorry, I could not process your request.")
    except Exception as e:
        logger.error("WhatsApp query error: %s", e)
        answer = "⚠️ Something went wrong on our end. Please try again."

    # Truncate if over WhatsApp limit
    if len(answer) > _WA_LIMIT:
        answer = answer[:_WA_LIMIT - 20] + "\n\n[…reply truncated]"

    return PlainTextResponse(_twiml_reply(answer), media_type="application/xml")
