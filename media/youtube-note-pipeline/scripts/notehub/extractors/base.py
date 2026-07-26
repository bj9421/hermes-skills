"""Base extractor interface and data models for NoteHub multi-source pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExtractResult:
    """Unified result from all extractors."""
    text: str                          # Main text content
    metadata: dict = field(default_factory=dict)  # Title, source, date, etc.
    source_type: str = ""              # youtube/url/pdf/text
    source_id: str = ""                # Unique ID (video_id, url hash, etc.)


class BaseExtractor(ABC):
    """Abstract base class for all source extractors."""

    @abstractmethod
    def detect(self, input_path: str) -> bool:
        """Detect if input_path matches this extractor type."""

    @abstractmethod
    def extract(self, input_path: str) -> ExtractResult:
        """Extract content from the source."""

    def get_metadata(self, input_path: str) -> dict:
        """Get metadata without full extraction. Default: empty dict."""
        return {}
