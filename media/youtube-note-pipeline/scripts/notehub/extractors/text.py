"""Text source extractor — reads local .md and .txt files."""

import hashlib
import os

from .base import BaseExtractor, ExtractResult


class TextExtractor(BaseExtractor):
    """Read local text files (.md, .txt, .rst, etc.)."""

    SUPPORTED_EXTS = {".md", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml", ".toml"}

    def detect(self, input_path: str) -> bool:
        if not os.path.exists(input_path):
            return False
        _, ext = os.path.splitext(input_path)
        return ext.lower() in self.SUPPORTED_EXTS

    def extract(self, input_path: str) -> ExtractResult:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"File not found: {input_path}")

        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        if not text.strip():
            raise ValueError(f"File is empty: {input_path}")

        basename = os.path.splitext(os.path.basename(input_path))[0]
        title = basename.replace("_", " ").replace("-", " ").title()
        file_hash = hashlib.md5(input_path.encode()).hexdigest()[:12]

        return ExtractResult(
            text=text,
            metadata={
                "title": title,
                "file_path": os.path.abspath(input_path),
                "chars": len(text),
            },
            source_type="text",
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
