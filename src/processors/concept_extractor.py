"""
ConceptExtractor — IP-SAKTI Domain (Phase 2)

Extracts entities and relationships from document chunks using a local
Ollama model (default: llama3.2:3b). Domain-adapted for Ayurveda IP &
regulatory corpus.

Entity types:
  Formulation, Ingredient, LegalInstrument, Jurisdiction,
  IPProtectionType, CasePrecedent, RegulatoryBody
  (+ generic Entity fallback)

Relation types:
  CONTAINS_INGREDIENT, DOCUMENTED_IN, APPLIES_IN, CITES,
  GOVERNED_BY, ELIGIBLE_FOR[INFERRED], RELATED_TO

Batches 6-8 chunks per call; SQLite cache; graceful Ollama fallback.
"""

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 7

# Allowlist guards against Cypher injection (D-15)
VALID_REL_TYPES = {
    "CONTAINS_INGREDIENT",
    "DOCUMENTED_IN",
    "APPLIES_IN",
    "CITES",
    "GOVERNED_BY",
    "ELIGIBLE_FOR",
    "RELATED_TO",
    "PART_OF",
}

# Few-shot example (Biological Diversity Act) for domain grounding
_FEW_SHOT = """
Example chunk:
[CHUNK_ID: ex_001]
Section 3 of the Biological Diversity Act, 2002: no person shall, without previous approval of the
National Biodiversity Authority, obtain any biological resource occurring in India.

Example output:
{
  "ex_001": {
    "entities": [
      {"name": "Biological Diversity Act 2002", "type": "LegalInstrument"},
      {"name": "National Biodiversity Authority", "type": "RegulatoryBody"},
      {"name": "India", "type": "Jurisdiction"}
    ],
    "relationships": [
      {"source": "National Biodiversity Authority", "target": "Biological Diversity Act 2002", "relation": "GOVERNED_BY"},
      {"source": "Biological Diversity Act 2002", "target": "India", "relation": "APPLIES_IN"}
    ],
    "inferred_relations": [],
    "suggested_category": "ip/national_law"
  }
}
"""


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
            r = parsed.get(c["chunk_id"], {
                "entities": [], "relationships": [],
                "inferred_relations": [], "suggested_category": "",
            })
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
            options={
                "temperature": 0.1,
                "num_predict": 1024,
                "repeat_penalty": 1.1,
            },
        )
        return response.get("response", "")

    def _build_prompt(self, chunks):
        """Domain-specific extraction prompt for IP/Ayurveda corpus."""
        chunk_text = "\n\n".join(
            f'[CHUNK_ID: {c["chunk_id"]}]\n{c["text"][:800]}'
            for c in chunks
        )
        return f"""You are an information extraction system for Ayurveda IP and regulatory law.

For each chunk extract:
1. Entities — use these types ONLY:
   Formulation, Ingredient, LegalInstrument, Jurisdiction, IPProtectionType,
   CasePrecedent, RegulatoryBody, Entity (generic fallback only).

2. Relationships:
   CONTAINS_INGREDIENT (Formulation→Ingredient)
   DOCUMENTED_IN (Formulation→LegalInstrument or CasePrecedent)
   APPLIES_IN (LegalInstrument→Jurisdiction)
   CITES (CasePrecedent→LegalInstrument)
   GOVERNED_BY (IPProtectionType or RegulatoryBody→LegalInstrument)
   RELATED_TO (generic)

3. ELIGIBLE_FOR relations (Formulation→IPProtectionType) go in "inferred_relations",
   NEVER in "relationships" — they are model-inferred, not legal facts.

4. suggested_category: one of ip/national_law, ip/international_law, ip/case_law,
   ip/pharmacopoeia, ip/tkdl_methodology, ip/manufacturing_licensing, ip/export_compliance, general.

{_FEW_SHOT}

Return ONLY valid JSON, no prose:
{{
  "<chunk_id>": {{
    "entities": [{{"name": "...", "type": "..."}}],
    "relationships": [{{"source": "...", "target": "...", "relation": "..."}}],
    "inferred_relations": [{{"source": "...", "target": "...", "relation": "ELIGIBLE_FOR", "confidence": "inferred"}}],
    "suggested_category": "..."
  }}
}}

Chunks:
{chunk_text}

JSON:"""

    @staticmethod
    def _parse_response(raw, chunks):
        """Parse LLM response; validate rel types against allowlist; separate inferred."""
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
            # Validate relation types — drop unknown (D-15)
            rels = [
                r for r in raw_entry.get("relationships", [])
                if r.get("relation") in VALID_REL_TYPES
            ]
            inferred = [
                r for r in raw_entry.get("inferred_relations", [])
                if r.get("relation") == "ELIGIBLE_FOR"
            ]
            result[cid] = {
                "entities": raw_entry.get("entities", []),
                "relationships": rels,
                "inferred_relations": inferred,
                "suggested_category": raw_entry.get("suggested_category", ""),
            }
        return result


    @staticmethod
    def _hash(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
