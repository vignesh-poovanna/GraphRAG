"""
Format converter — normalizes PDF/HTML/DOCX/TXT to Markdown.

Design: convert everything to Markdown *before* document_processor.py.
That way the existing frontmatter parsing and chunking stay untouched;
we only widen what can feed into them.

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
        try:
            from docling.document_converter import DocumentConverter as DoclingConverter  # type: ignore
            converter = DoclingConverter()
            result = converter.convert(str(filepath))
            md = result.document.export_to_markdown()
        except ImportError:
            logger.warning("docling not installed; falling back to raw text for PDF")
            md = self._raw_fallback(filepath)
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
        """If md already has frontmatter, leave it alone. Otherwise inject minimal block."""
        if self._FM_RE.match(md):
            return md
        title = self._extract_title(md) or Path(filepath).stem.replace("_", " ").replace("-", " ").title()
        fm = "---\ntitle: \"{title}\"\ncategory: uncategorized\n---\n\n".format(title=title)
        return fm + md

    @staticmethod
    def _extract_title(md):
        """Pull title from first # heading."""
        m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
        return m.group(1).strip() if m else ""

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
