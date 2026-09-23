"""
citation_formatter.py — Phase 4

Turns a retrieved chunk's metadata into a proper legal-style citation string
and a structured {claim_text, citation, source_snippet} object for the
frontend's inline-reference rendering.

Citation examples:
  "Biological Diversity Act, 2002, Section 3 (India)"
  "Turmeric Wound-Healing Patent Revocation, USPTO, 1997"
  "Nagoya Protocol on Access and Benefit-Sharing, Article 5 (International)"
"""


import os

def format_citation(metadata: dict) -> str:
    """
    Render a legal-style citation string from a chunk's metadata dict.

    Expected metadata keys (all optional with graceful fallback):
      act_or_source_name, section, year, jurisdiction, document_type,
      title, category, path
    """
    raw_path = metadata.get("path", "")
    fallback_name = os.path.splitext(os.path.basename(raw_path))[0] if raw_path else "Unknown Source"
    name = (
        metadata.get("act_or_source_name")
        or metadata.get("title")
        or fallback_name
    )
    year = metadata.get("year", "")
    section = metadata.get("section", "")
    jurisdiction = metadata.get("jurisdiction", "")
    doc_type = metadata.get("document_type", "")

    parts = [name]
    if year:
        parts[0] = f"{name}, {year}"
    if section:
        parts.append(f"Section {section}")
    if jurisdiction:
        parts.append(f"({jurisdiction})")

    return ", ".join(parts)


def format_source_object(chunk: dict, claim_text: str = "") -> dict:
    """
    Build the structured citation object returned in API responses.

    Returns:
        {
          "claim_text":     str — the relevant sentence(s) from the answer,
          "citation":       str — legal-style citation,
          "source_snippet": str — the raw chunk text for provenance,
          "metadata":       dict — all metadata fields for frontend use,
          "doc_type":       str — statute | case | pharmacopoeia | guideline | general,
          "tag":            str — "[CLEAR]" | "[AMBIGUOUS]" | "[INFERRED]" (default [CLEAR])
        }
    """
    metadata = dict(chunk.get("metadata") or {})
    doc = chunk.get("document") or {}
    if isinstance(doc, dict):
        for k, v in doc.items():
            if k not in metadata and v:
                metadata[k] = v

    # Also pick up flat payload fields (Qdrant result structure)
    for key in ("jurisdiction", "act_or_source_name", "year", "language",
                "document_type", "title", "category", "section", "stage"):
        if key not in metadata and key in chunk:
            metadata[key] = chunk[key]

    from src.utils.citation_index import enrich_with_url
    obj = {
        "claim_text":     claim_text,
        "citation":       format_citation(metadata),
        "source_snippet": chunk.get("text", ""),
        "metadata":       metadata,
        "doc_type":       metadata.get("document_type", "general"),
        "tag":            "[CLEAR]",  # overridden by Phase 6 confidence tagger
        "score":          chunk.get("score"),
    }
    return enrich_with_url(obj)
