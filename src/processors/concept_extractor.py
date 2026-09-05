"""
ConceptExtractor — Part B2

Extracts entities and relationships from document chunks using a local
Ollama model (default: llama3.2:3b). Runs as an optional post-processing
layer — never blocks the main ingestion pipeline.

Key design points:
- Batches 6-8 chunks per Ollama call to minimise fixed per-call overhead
  on CPU-only hardware (see plan Part C3).
- Content-hash SQLite cache: unchanged chunks cost zero LLM calls on
  re-runs.
- Falls back gracefully on Ollama unavailability — callers get empty
  entity lists rather than exceptions.
"""

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Default batch size: 6-8 chunks per call is the sweet spot on 3B models
# (cuts total call count by ~7x vs one call per chunk).
DEFAULT_BATCH_SIZE = 7


class ConceptExtractor:
    """Extract concepts/entities from chunks via a local Ollama LLM."""

    def __init__(
        self,
        model="llama3.2:3b",
        host="http://localhost:11434",
        cache_path="concept_cache.db",
        batch_size=DEFAULT_BATCH_SIZE,
    ):
        self.model = model
        self.host = host
        self.batch_size = batch_size
        self._ollama = None  # lazy-init

        cache_path = Path(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache = sqlite3.connect(str(cache_path))
        self._cache.execute(
            "CREATE TABLE IF NOT EXISTS cache (hash TEXT PRIMARY KEY, result TEXT)"
        )
        self._cache.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_batch(self, chunks):
        """
        Extract entities and relationships for a list of chunks.

        Args:
            chunks: list of {'chunk_id': str, 'text': str}

        Returns:
            dict of {chunk_id: {'entities': [...], 'relationships': [...]}}
            Each entity: {'name': str, 'type': str}
            Each relationship: {'source': str, 'target': str, 'relation': str}
        """
        results = {}
        uncached = []

        for c in chunks:
            h = self._hash(c["text"])
            row = self._cache.execute(
                "SELECT result FROM cache WHERE hash=?", (h,)
            ).fetchone()
            if row:
                results[c["chunk_id"]] = json.loads(row[0])
            else:
                uncached.append((c, h))

        if uncached:
            # Process in sub-batches of self.batch_size
            for i in range(0, len(uncached), self.batch_size):
                sub = uncached[i : i + self.batch_size]
                self._process_uncached_batch(sub, results)

        return results

    def is_available(self):
        """Return True if Ollama is reachable. Non-raising."""
        try:
            client = self._get_client()
            client.list()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-init the ollama client (import only when needed)."""
        if self._ollama is None:
            try:
                import ollama  # type: ignore
                self._ollama = ollama.Client(host=self.host)
            except ImportError:
                raise RuntimeError(
                    "ollama package not installed. Run: pip install ollama"
                )
        return self._ollama

    def _process_uncached_batch(self, sub_batch, results):
        """Call Ollama for a sub-batch, parse, cache, and merge into results."""
        chunks_only = [c for c, _ in sub_batch]
        try:
            prompt = self._build_prompt(chunks_only)
            raw = self._call_ollama(prompt)
            parsed = self._parse_response(raw, chunks_only)
        except Exception as exc:
            logger.warning("Ollama call failed (%s); skipping batch", exc)
            parsed = {}

        for c, h in sub_batch:
            r = parsed.get(c["chunk_id"], {"entities": [], "relationships": []})
            results[c["chunk_id"]] = r
            try:
                self._cache.execute(
                    "INSERT OR REPLACE INTO cache VALUES (?,?)",
                    (h, json.dumps(r)),
                )
            except Exception as e:
                logger.warning("Cache write failed: %s", e)

        self._cache.commit()

    def _call_ollama(self, prompt):
        client = self._get_client()
        response = client.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": 0.0},  # deterministic output for structured extraction
        )
        return response.get("response", "")

    def _build_prompt(self, chunks):
        """
        Build a single prompt for multiple chunks.
        Asks for JSON output keyed by chunk_id.
        suggested_category is a free field — used by D1 to auto-classify docs
        with no category frontmatter. Zero extra LLM calls (same batch, one extra field).
        """
        chunk_text = "\n\n".join(
            f'[CHUNK_ID: {c["chunk_id"]}]\n{c["text"][:800]}'
            for c in chunks
        )
        return f"""You are an information extraction system. For each chunk below, extract:
1. Named entities (people, places, organizations, concepts, technical terms).
2. Relationships between those entities within the same chunk.
3. A short category label (1-3 words) that best describes the chunk's topic domain.

Return ONLY a valid JSON object. No prose. Format:
{{
  "<chunk_id>": {{
    "entities": [{{"name": "...", "type": "concept|person|org|place|other"}}],
    "relationships": [{{"source": "...", "target": "...", "relation": "..."}}],
    "suggested_category": "..."
  }},
  ...
}}

Chunks:
{chunk_text}

JSON:"""

    @staticmethod
    def _parse_response(raw, chunks):
        """
        Parse the LLM JSON response. Falls back to empty on any parse failure.
        Tries to extract a JSON object even if surrounded by prose.
        """
        raw = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r"```$", "", raw.strip(), flags=re.MULTILINE)

        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            logger.warning("No JSON object found in Ollama response")
            return {}

        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error in Ollama response: %s", e)
            return {}

        result = {}
        for c in chunks:
            cid = c["chunk_id"]
            raw_entry = data.get(cid, {})
            result[cid] = {
                "entities": raw_entry.get("entities", []),
                "relationships": raw_entry.get("relationships", []),
                "suggested_category": raw_entry.get("suggested_category", ""),
            }
        return result


    @staticmethod
    def _hash(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
