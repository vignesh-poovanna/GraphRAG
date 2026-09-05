import os
import sys
from pathlib import Path
sys.path.insert(0, '.')
from src.config import Config
from src.processors.document_processor import DocumentProcessor
from src.processors.format_converter import FormatConverter

cfg = Config()
dp = DocumentProcessor(cfg)
fc = FormatConverter()

docs_dir = Path('your_docs_here')
total = 0
for p in sorted(docs_dir.iterdir()):
    if p.name.startswith('.'):
        continue
    try:
        md_text, st = fc.convert(p)
        meta, chunks = dp.process_document(str(p), text=md_text, source_type=st)
        total += len(chunks)
        print(f"{p.name:45s} -> {len(chunks):3d} chunks (source={st})")
    except Exception as e:
        print(f"{p.name:45s} -> ERROR: {e}")
print(f"TOTAL CHUNKS ACROSS ALL FILES: {total}")


