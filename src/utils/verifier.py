"""
verifier.py — Phase 9/10 post-generation guardrail

After synthesis, checks that every [CLEAR] claim in the answer is
actually grounded in one of the retrieved chunks.

Algorithm:
  For each [CLEAR]-tagged sentence in the answer:
    - Extract the longest noun phrase / key term (crude: longest 4-gram)
    - Check if it appears (case-insensitive) in any retrieved chunk text
    - If NOT found → downgrade tag to [AMBIGUOUS] and log a warning

This is a pure string-overlap check — no LLM call. Runs in < 5 ms.
It's the "belt" to the system-prompt "suspenders".
"""

import logging
import re

logger = logging.getLogger(__name__)

_CLEAR_SENT_RE = re.compile(r'\[CLEAR\]\s+([^.\n]+[.\n]?)')
_AMBIG_TAG     = "[AMBIGUOUS]"


def verify_and_downgrade(answer: str, chunks: list[dict]) -> str:
    """
    Check [CLEAR] claims against retrieved chunks.
    Downgrade to [AMBIGUOUS] any claim not found in context.

    Args:
        answer: synthesised answer string with [CLEAR]/[AMBIGUOUS]/[INFERRED] tags
        chunks: list of result dicts from hybrid_search (must have 'text' key)

    Returns:
        Patched answer string with downgraded tags where verification failed.
    """
    if "[CLEAR]" not in answer:
        return answer

    # Build a single lowercased search corpus from all chunk texts
    corpus = " ".join((c.get("text") or "") for c in chunks).lower()

    def _check_and_replace(m: re.Match) -> str:
        sentence = m.group(1)
        probe = _longest_ngram(sentence, n=4).lower()
        if probe and probe not in corpus:
            logger.warning("CLEAR claim not found in context, downgrading: %r", probe)
            return f"{_AMBIG_TAG} {sentence}"
        return m.group(0)   # keep original

    return _CLEAR_SENT_RE.sub(_check_and_replace, answer)


def _longest_ngram(text: str, n: int = 4) -> str:
    """Extract the longest n-gram of content words from text as a probe string."""
    words = re.findall(r'\b[A-Za-z]{3,}\b', text)
    if not words:
        return ""
    # Use the middle n words (avoids leading/trailing connectives)
    mid = max(0, len(words) // 2 - n // 2)
    return " ".join(words[mid: mid + n])
