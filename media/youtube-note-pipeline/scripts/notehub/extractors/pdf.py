"""PDF source extractor — pulls text and tables from PDF files.

Uses pymupdf4llm to convert PDF to Markdown (preserves tables).
"""

import hashlib
import os
import sys

from .base import BaseExtractor, ExtractResult


class PDFExtractor(BaseExtractor):
    """Extract text and tables from PDF files."""

    def detect(self, input_path: str) -> bool:
        return input_path.lower().endswith(".pdf")

    def extract(self, input_path: str) -> ExtractResult:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"PDF not found: {input_path}")

        print(f"[INFO] Extracting PDF: {input_path}", file=sys.stderr)

        try:
            import pymupdf4llm
            text = pymupdf4llm.to_markdown(input_path)
        except ImportError:
            raise ImportError("pymupdf4llm not installed. Run: uv pip install pymupdf4llm")
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {e}")

        if not text or len(text.strip()) < 10:
            raise ValueError(f"PDF extraction produced empty content: {input_path}")

        # Extract title from filename
        basename = os.path.splitext(os.path.basename(input_path))[0]
        title = basename.replace("_", " ").replace("-", " ").title()

        file_hash = hashlib.md5(input_path.encode()).hexdigest()[:12]

        return ExtractResult(
            text=text,
            metadata={
                "title": title,
                "file_path": os.path.abspath(input_path),
                "pages": text.count("\f") + 1,  # form feed = page break
                "chars": len(text),
            },
            source_type="pdf",
            source_id=file_hash,
        )

    def get_metadata(self, input_path: str) -> dict:
        basename = os.path.splitext(os.path.basename(input_path))[0]
        file_hash = hashlib.md5(input_path.encode()).hexdigest()[:12]
        return {
            "title": basename,
            "file_path": os.path.abspath(input_path),
            "source_id": file_hash,
        }
