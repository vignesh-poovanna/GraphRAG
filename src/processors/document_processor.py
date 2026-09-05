"""
Document processor for parsing and chunking documents.

Smart chunking strategy (CHUNKING_STRATEGY=structure_aware, default):
  1. Split on Markdown heading boundaries (##, ###).
  2. Protect table and code-fence blocks — never split inside them.
  3. If a section exceeds MAX_CHUNK_SIZE, sub-split with the original
     fixed-size+overlap logic (CHUNK_SIZE / CHUNK_OVERLAP env vars).
  Rollback: set CHUNKING_STRATEGY=fixed to use the original behaviour.

Also accepts pre-converted markdown text via process_document(text=...) so
FormatConverter can pipe non-md files through without touching disk.
"""

import re
import os
import uuid
import yaml
import logging

logger = logging.getLogger(__name__)



class DocumentProcessor:
    """Process documents into chunks with metadata."""

    SUPPORTED_EXTENSIONS = {'.md', '.markdown', '.pdf', '.txt', '.html', '.htm', '.docx'}

    def __init__(self, config):
        self.config = config
        self.chunk_size = config.get('chunking.chunk_size', 600)
        self.chunk_overlap = config.get('chunking.chunk_overlap', 100)
        self.strategy = config.get('chunking.strategy', 'structure_aware')
        self.max_chunk_size = config.get('chunking.max_chunk_size', 1000)
        self.keep_tables_atomic = config.get('chunking.keep_tables_atomic', True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_document(self, file_path, text=None, source_type="md"):
        """
        Process a document into chunks with metadata.

        Args:
            file_path: path on disk (used for metadata; required even when text is provided).
            text:      pre-converted Markdown string (optional). When None the file is read directly.
            source_type: one of "md", "pdf", "txt", "html", "docx" — stored in chunk metadata.
        """
        logger.info("Processing document: %s", file_path)

        if text is None:
            # Direct file read path (md/markdown only — FormatConverter handles the rest)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Document file not found: {file_path}")
            _, ext = os.path.splitext(file_path)
            if ext.lower() not in {'.md', '.markdown'}:
                raise ValueError(
                    f"Pass text= for non-markdown files or route through FormatConverter. Got: {ext}"
                )
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

        metadata, body = self._extract_front_matter(text)

        metadata['path'] = str(file_path)
        metadata['source_type'] = source_type
        if 'id' not in metadata:
            metadata['id'] = f"doc_{uuid.uuid4().hex[:8]}"

        if not metadata.get('title'):
            metadata['title'] = self._extract_title_from_text(body) or os.path.basename(str(file_path))

        if not metadata.get('category'):
            dir_path = os.path.dirname(str(file_path))
            base_dir = os.path.basename(dir_path)
            metadata['category'] = base_dir if base_dir else 'uncategorized'

        chunks = self._chunk_text(body)
        logger.info("Document chunked into %d parts (strategy=%s)", len(chunks), self.strategy)

        chunk_objects = []
        for i, (chunk_text, chunk_type) in enumerate(chunks):
            chunk_objects.append({
                'id': str(uuid.uuid4()),
                'text': chunk_text,
                'doc_id': metadata['id'],
                'position': i,
                'chunk_type': chunk_type,
                'source_type': source_type,
                'metadata': metadata,
            })

        return metadata, chunk_objects

    def process_directory(self, directory_path, recursive=True):
        """Process all supported documents in a directory."""
        logger.info("Processing directory: %s (recursive: %s)", directory_path, recursive)

        # Import here to avoid circular import — FormatConverter is only needed
        # for non-md files; md files go through the direct path.
        from src.processors.format_converter import FormatConverter
        converter = FormatConverter()

        files = []
        if recursive:
            for root, _, filenames in os.walk(directory_path):
                for filename in filenames:
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in self.SUPPORTED_EXTENSIONS:
                        files.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(directory_path):
                fp = os.path.join(directory_path, filename)
                if os.path.isfile(fp):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in self.SUPPORTED_EXTENSIONS:
                        files.append(fp)

        logger.info("Found %d documents to process", len(files))

        all_docs, all_chunks = [], []
        for file_path in files:
            try:
                _, ext = os.path.splitext(file_path)
                if ext.lower() in {'.md', '.markdown'}:
                    metadata, chunks = self.process_document(file_path, source_type="md")
                else:
                    md_text, source_type = converter.convert(file_path)
                    metadata, chunks = self.process_document(file_path, text=md_text, source_type=source_type)
                all_docs.append(metadata)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error("Error processing %s: %s", file_path, e)

        logger.info("Processed %d documents with %d total chunks", len(all_docs), len(all_chunks))
        return all_docs, all_chunks

    # ------------------------------------------------------------------
    # Front matter
    # ------------------------------------------------------------------

    def _extract_front_matter(self, content):
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if m:
            try:
                meta = yaml.safe_load(m.group(1))
                if meta and isinstance(meta, dict):
                    return meta, m.group(2)
            except yaml.YAMLError as e:
                logger.warning("YAML front matter parse error: %s", e)
        return {'title': '', 'category': ''}, content

    def _extract_title_from_text(self, text):
        m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
        return m.group(1).strip() if m else ''

    # ------------------------------------------------------------------
    # Chunking dispatch
    # ------------------------------------------------------------------

    def _chunk_text(self, text):
        """Returns list of (chunk_text, chunk_type) tuples."""
        if self.strategy == 'fixed':
            return [(c, 'text') for c in self._fixed_chunks(text)]
        return self._structure_aware_chunks(text)

    # ------------------------------------------------------------------
    # Structure-aware chunker
    # ------------------------------------------------------------------

    def _structure_aware_chunks(self, text):
        """
        Line-walk state machine:
        - Tracks whether we're inside a code fence or table block.
        - Flushes the current section on a new ## / ### heading.
        - Marks code and table sections with their chunk_type.
        - Sub-splits oversized text sections using fixed-size logic.
        """
        lines = text.splitlines(keepends=True)
        chunks = []
        current_lines = []
        current_type = 'text'   # type of the *current* section being built
        in_code = False
        in_table = False

        def flush(buf, kind):
            """Emit buf as one or more chunks of the given kind."""
            body = "".join(buf).strip()
            if not body:
                return
            if kind == 'text' and len(body) > self.max_chunk_size:
                for sub in self._fixed_chunks(body):
                    if sub.strip():
                        chunks.append((sub, 'text'))
            else:
                chunks.append((body, kind))

        for line in lines:
            stripped = line.strip()

            # --- code fence toggle ---
            if stripped.startswith("```"):
                if not in_code:
                    # Starting a code block: flush preceding text, start code section
                    flush(current_lines, current_type)
                    current_lines = [line]
                    current_type = 'code'
                    in_code = True
                else:
                    # Closing the code block: include closing fence, flush
                    current_lines.append(line)
                    flush(current_lines, 'code')
                    current_lines = []
                    current_type = 'text'
                    in_code = False
                continue

            if in_code:
                current_lines.append(line)
                continue

            # --- table detection ---
            is_table_line = stripped.startswith("|")
            if is_table_line and not in_table:
                # If current_lines only contains a heading introducing this table, keep it with the table
                lines_non_empty = [l.strip() for l in current_lines if l.strip()]
                if len(lines_non_empty) == 1 and re.match(r'^#{1,4}\s+', lines_non_empty[0]):
                    current_lines.append(line)
                else:
                    flush(current_lines, current_type)
                    current_lines = [line]
                current_type = 'table'
                in_table = True
                continue
            if not is_table_line and in_table:
                # Table ended
                flush(current_lines, 'table')
                current_lines = []
                current_type = 'text'
                in_table = False
                # Fall through to process this non-table line normally

            if in_table:
                current_lines.append(line)
                continue

            # --- heading detection (## or ###) ---
            if re.match(r'^#{2,}\s+', stripped):
                flush(current_lines, current_type)
                current_lines = [line]
                current_type = 'text'
                continue

            current_lines.append(line)

        # Flush whatever remains
        flush(current_lines, current_type)

        return chunks if chunks else [("", "text")]

    # ------------------------------------------------------------------
    # Boundary-aware chunker (never slices mid-word or mid-sentence)
    # ------------------------------------------------------------------

    def _fixed_chunks(self, text):
        chunks = []
        start = 0
        while start < len(text):
            if len(text) - start <= self.chunk_size:
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            ideal_end = start + self.chunk_size
            end = -1

            # 1. Paragraph boundary (\n\n) within [ideal_end - 150, ideal_end + 150]
            pb = text.rfind('\n\n', max(start, ideal_end - 150), min(len(text), ideal_end + 150))
            if pb != -1 and pb > start:
                end = pb + 2

            # 2. Sentence boundary ([.!?]\s+) within [ideal_end - 200, ideal_end + 100]
            if end == -1:
                w_start = max(start, ideal_end - 200)
                w_end = min(len(text), ideal_end + 100)
                matches = list(re.finditer(r'[.!?]\s+', text[w_start:w_end]))
                if matches:
                    best_m = min(matches, key=lambda m: abs((w_start + m.end()) - ideal_end))
                    end = w_start + best_m.end()

            # 3. Word boundary: snap to nearest space so words are NEVER sliced in half
            if end == -1:
                space_idx = text.rfind(' ', max(start, ideal_end - 100), min(len(text), ideal_end + 40))
                if space_idx != -1 and space_idx > start:
                    end = space_idx + 1
                else:
                    end = min(ideal_end, len(text))

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break

            # Advance start with overlap, snapping forward to next word boundary
            next_start = max(start + 1, end - self.chunk_overlap)
            if next_start < end:
                space_fwd = text.find(' ', next_start, min(end, next_start + 30))
                if space_fwd != -1:
                    next_start = space_fwd + 1
            start = next_start

        return chunks