"""Auto-detect source type and return the appropriate extractor."""

from .base import BaseExtractor
from .youtube import YouTubeExtractor
from .url import URLExtractor
from .pdf import PDFExtractor
from .text import TextExtractor

# Ordered by priority — first match wins
_EXTRACTORS = [
    YouTubeExtractor(),
    URLExtractor(),
    PDFExtractor(),
    TextExtractor(),
]


def detect_source(input_path: str) -> BaseExtractor:
    """Detect source type and return the matching extractor.

    Priority: YouTube > URL > PDF > Text

    Raises:
        ValueError: if no extractor matches the input.
    """
    for ext in _EXTRACTORS:
        if ext.detect(input_path):
            return ext

    raise ValueError(
        f"Cannot detect source type for: {input_path}\n"
        f"Supported: YouTube URLs, http(s) URLs, .pdf files, .md/.txt files"
    )
