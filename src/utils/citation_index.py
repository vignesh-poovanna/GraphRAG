"""
citation_index.py — Phase 9 helper

Loads data/citations_index.txt at startup and enriches citation objects with URLs.
File format (TSV, one line per document):
    <document_name_or_act>\t<url>

Example:
    Biological Diversity Act 2002\thttps://legislative.dept.gov.in/sites/default/files/BD2002.pdf
    Patents Act 1970\thttps://ipindia.gov.in/writereaddata/Portal/ev/sections_patents_act_1970.pdf

The loader does a soft substring match so "Patents Act 1970, Section 3(p)" correctly
resolves to the Patents Act 1970 entry.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_INDEX: dict[str, str] = {}   # key: lowercased name, value: url


def load_citations_index(path: str = "./data/citations_index.txt") -> int:
    """Load the index file. Returns number of entries loaded. Safe to call multiple times."""
    global _INDEX
    p = Path(path)
    if not p.exists():
        logger.info("No citations_index.txt found at %s — URL enrichment disabled", path)
        return 0
    count = 0
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                name, url = parts[0].strip(), parts[1].strip()
                _INDEX[name.lower()] = url
                count += 1
    logger.info("Loaded %d citation URL entries from %s", count, path)
    return count


def enrich_with_url(citation_obj: dict) -> dict:
    """
    Add a 'url' key to a format_source_object() dict if a match is found.
    Mutates in place and also returns the dict.
    Matching is substring: if any index key appears in the citation text, it wins.
    """
    if not _INDEX:
        return citation_obj

    citation_text = (citation_obj.get("citation") or "").lower()
    act_name = (citation_obj.get("act_or_source_name") or "").lower()
    for key, url in _INDEX.items():
        if key in citation_text or key in act_name:
            citation_obj["url"] = url
            break
    return citation_obj
