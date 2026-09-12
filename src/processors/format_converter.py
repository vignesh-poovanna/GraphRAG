"""
Format converter — normalizes PDF/HTML/DOCX/TXT to Markdown.

Design: convert everything to Markdown *before* document_processor.py.
That way the existing frontmatter parsing and chunking stay untouched;
we only widen what can feed into them.

Supports IP-SAKTI corpus metadata: jurisdiction, act_or_source_name, year, language, document_type, stage.

Optional deps (import lazily so missing libs only fail for that file type):
  docling   — PDF
  markitdown — DOCX
  trafilatura — HTML boilerplate stripping
"""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FormatConverter:
    """Convert various file formats to clean Markdown with injected frontmatter."""

    SUPPORTED = {".md", ".markdown", ".pdf", ".txt", ".html", ".htm", ".docx"}

    def convert(self, filepath: Path) -> tuple:
        """
        Returns (markdown_text, source_type).
        markdown_text always has YAML frontmatter at the top.
        source_type is one of: md, pdf, txt, html, docx.
        Raises ValueError for unsupported extensions.
        On per-converter failure: logs and falls back to raw text read.
        """
        filepath = Path(filepath)
        ext = filepath.suffix.lower()

        if ext not in self.SUPPORTED:
            raise ValueError(f"Unsupported file type: {ext}")

        try:
            if ext in (".md", ".markdown"):
                md = filepath.read_text(encoding="utf-8")
                return self._ensure_frontmatter(md, filepath), "md"
            elif ext == ".pdf":
                return self._convert_pdf(filepath), "pdf"
            elif ext == ".txt":
                return self._convert_txt(filepath), "txt"
            elif ext in (".html", ".htm"):
                return self._convert_html(filepath), "html"
            elif ext == ".docx":
                return self._convert_docx(filepath), "docx"
        except Exception as exc:
            logger.warning(
                "Converter failed for %s (%s); falling back to raw text read",
                filepath, exc
            )
            raw = self._raw_fallback(filepath)
            return self._ensure_frontmatter(raw, filepath), ext.lstrip(".")

    # ------------------------------------------------------------------
    # Per-format converters
    # ------------------------------------------------------------------

    def _convert_pdf(self, filepath):
        md = ""
        # 1. Try pymupdf4llm (extracts rich Markdown, tables, headings, and images)
        try:
            import pymupdf4llm
            md = pymupdf4llm.to_markdown(str(filepath))
            logger.info("Converted PDF %s via pymupdf4llm (%d chars)", filepath, len(md))
        except ImportError:
            logger.debug("pymupdf4llm not installed; checking other converters")
        except Exception as exc:
            logger.warning("pymupdf4llm failed for %s: %s", filepath, exc)

        # 2. Try docling if pymupdf4llm did not produce text
        if not md:
            try:
                from docling.document_converter import DocumentConverter as DoclingConverter  # type: ignore
                converter = DoclingConverter()
                result = converter.convert(str(filepath))
                md = result.document.export_to_markdown()
                logger.info("Converted PDF %s via docling (%d chars)", filepath, len(md))
            except ImportError:
                logger.debug("docling not installed")
            except Exception as exc:
                logger.warning("docling failed for %s: %s", filepath, exc)

        # 3. Try pypdf text extraction fallback
        if not md:
            try:
                import pypdf
                reader = pypdf.PdfReader(str(filepath))
                pages = [page.extract_text() or "" for page in reader.pages]
                md = "\n\n".join(pages).strip()
                logger.info("Extracted text from PDF %s via pypdf (%d chars)", filepath, len(md))
            except Exception as exc:
                logger.error("All PDF converters failed for %s: %s", filepath, exc)
                md = ""

        return self._ensure_frontmatter(md, filepath)

    def _convert_txt(self, filepath):
        raw = filepath.read_text(encoding="utf-8", errors="replace")
        return self._ensure_frontmatter(raw, filepath)

    def _convert_html(self, filepath):
        try:
            import trafilatura  # type: ignore
            html = filepath.read_text(encoding="utf-8", errors="replace")
            extracted = trafilatura.extract(
                html,
                output_format="markdown",
                include_tables=True,
                include_links=False,
            )
            md = extracted or self._html_strip_fallback(html)
        except ImportError:
            logger.warning("trafilatura not installed; using basic HTML strip for HTML")
            html = filepath.read_text(encoding="utf-8", errors="replace")
            md = self._html_strip_fallback(html)
        return self._ensure_frontmatter(md, filepath)

    def _convert_docx(self, filepath):
        try:
            from markitdown import MarkItDown  # type: ignore
            mid = MarkItDown()
            result = mid.convert(str(filepath))
            md = result.text_content
        except ImportError:
            logger.warning("markitdown not installed; falling back to raw text for DOCX")
            md = self._raw_fallback(filepath)
        return self._ensure_frontmatter(md, filepath)

    # ------------------------------------------------------------------
    # Frontmatter injection
    # ------------------------------------------------------------------

    _FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

    def _ensure_frontmatter(self, md, filepath):
        """If md already has frontmatter, leave it alone. Otherwise inject IP-SAKTI corpus metadata."""
        if self._FM_RE.match(md):
            return md

        filepath = Path(filepath)
        title = self._extract_title(md) or filepath.stem.replace("_", " ").replace("-", " ").title()
        path_str = str(filepath).lower()

        # Map corpus folder → (category, document_type, jurisdiction)
        _MAP = {
            "national_law":            ("ip/national_law",            "statute",       "India"),
            "international_law":       ("ip/international_law",       "statute",       "International"),
            "case_law":                ("ip/case_law",                "case",          "Various"),
            "pharmacopoeia":           ("ip/pharmacopoeia",           "pharmacopoeia", "India"),
            "tkdl_methodology":        ("ip/tkdl_methodology",        "guideline",     "India"),
            "manufacturing_licensing": ("ip/manufacturing_licensing", "guideline",     "India"),
            "export_compliance":       ("ip/export_compliance",       "guideline",     "Various"),
        }
        category, document_type, jurisdiction = "general", "general", "Unknown"
        for folder, (cat, dtype, jur) in _MAP.items():
            if folder in path_str:
                category, document_type, jurisdiction = cat, dtype, jur
                break

        # Year from filename stem (e.g. "biodiversity_act_2002")
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filepath.stem)
        year = year_match.group(1) if year_match else ""

        # stage is meaningful only for manufacturing_licensing; empty string elsewhere
        stage = "application" if "manufacturing_licensing" in path_str else ""

        fm = (
            f'---\n'
            f'title: "{title}"\n'
            f'category: {category}\n'
            f'document_type: {document_type}\n'
            f'jurisdiction: "{jurisdiction}"\n'
            f'act_or_source_name: "{title}"\n'
            f'year: "{year}"\n'
            f'language: "en"\n'
            f'stage: "{stage}"\n'
            f'---\n\n'
        )
        return fm + md

    @staticmethod
    def _extract_title(md):
        """Pull title from first # heading, cleaning markdown bold/italic syntax."""
        m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
        if m:
            title = m.group(1).strip()
            # Clean markdown bold/italic/backtick artifacts
            title = re.sub(r"[*_`#]", "", title).strip()
            return title
        return ""

    # ------------------------------------------------------------------
    # Fallbacks
    # ------------------------------------------------------------------

    @staticmethod
    def _raw_fallback(filepath):
        """Last-resort: read file as text, ignore decode errors."""
        try:
            return Path(filepath).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def _html_strip_fallback(html):
        """Minimal tag stripper when trafilatura isn't available."""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        return re.sub(r"\s{2,}", "\n", text).strip()
