"""URL source extractor — pulls text content from web pages.

Uses urllib to fetch HTML, then strips tags to extract readable text.
For JavaScript-heavy sites, falls back to a simpler extraction.
"""

import hashlib
import re
import sys
import urllib.request
import urllib.error
from html.parser import HTMLParser

from .base import BaseExtractor, ExtractResult


class _HTMLStripper(HTMLParser):
    """Strip HTML tags, keep text content."""

    SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript"}
    BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr", "blockquote"}

    def __init__(self):
        super().__init__()
        self.result = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.result.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.result.append(text)

    def get_text(self):
        raw = " ".join(self.result)
        # Collapse multiple newlines/spaces
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        return raw.strip()


def _strip_html(html: str) -> str:
    """Remove HTML tags and return clean text."""
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch URL content as HTML string."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NoteHub/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _extract_title_from_html(html: str) -> str:
    """Extract <title> from HTML."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return _strip_html(m.group(1)).strip()[:200]
    return ""


class URLExtractor(BaseExtractor):
    """Extract readable text from web pages."""

    def detect(self, input_path: str) -> bool:
        return input_path.startswith("http://") or input_path.startswith("https://")

    def extract(self, input_path: str) -> ExtractResult:
        print(f"[INFO] Fetching URL: {input_path}", file=sys.stderr)
        html = _fetch_url(input_path)
        text = _strip_html(html)
        title = _extract_title_from_html(html)

        if len(text) < 50:
            raise ValueError(f"Extracted text too short ({len(text)} chars) — page may require JavaScript")

        url_hash = hashlib.md5(input_path.encode()).hexdigest()[:12]

        return ExtractResult(
            text=text,
            metadata={
                "title": title or input_path,
                "url": input_path,
                "fetched_chars": len(text),
            },
            source_type="url",
            source_id=url_hash,
        )

    def get_metadata(self, input_path: str) -> dict:
        url_hash = hashlib.md5(input_path.encode()).hexdigest()[:12]
        return {"url": input_path, "source_id": url_hash}
