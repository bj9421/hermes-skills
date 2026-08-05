"""URL source extractor — pulls text content from web pages.

Uses urllib to fetch HTML, then strips tags to extract readable text.
For JavaScript-heavy sites, falls back to a simpler extraction.

小紅書（2026-08-05）：xhslink 短鏈 / xiaohongshu.com 在台灣被 DNS 污染，
urllib 直接抓會 SSL CERTIFICATE_VERIFY_FAILED（self-signed）。改走專用路徑：
短鏈 302 → DoH(dns.google) 查 www 子域真實 IP → curl --resolve 繞 DNS → parse
__INITIAL_STATE__ 拿 title / desc / tagList（解法搬自 bookmark-manager llm_enhance.py）。
"""

import hashlib
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from html.parser import HTMLParser

from .base import BaseExtractor, ExtractResult

# 小紅書手機 UA（2026-08-05，與 bookmark-manager 一致）
_XHS_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
           'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')


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


def _is_xhs_url(url: str) -> bool:
    """小紅書短鏈或真實網域（2026-08-05）。"""
    return 'xhslink.com' in url or 'xiaohongshu.com' in url


def _fetch_xhs(url: str, timeout: int = 30) -> str:
    """小紅書專用抓取：短鏈 302 → DoH 查 IP → curl --resolve → __INITIAL_STATE__ 文字。

    解法搬自 bookmark-manager llm_enhance.py fetch_xiaohongshu_meta()。
    回傳可讀文字（標題 + 描述 + 標籤）。全部失敗 raise ValueError。
    """
    # 1. curl 追蹤短鏈 → 真實 note URL（xhslink 回 302，urllib 不跟且 SSL 失敗）
    try:
        r = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{url_effective}',
             '-A', _XHS_UA, '--max-time', '15', '-k', '-L', url],
            capture_output=True, text=True, timeout=20)
        resolved = r.stdout.strip()
    except Exception as e:
        raise ValueError(f'小紅書短鏈解析失敗: {e}')
    if not resolved or 'xiaohongshu.com' not in resolved:
        raise ValueError(f'小紅書短鏈解析結果異常: {resolved[:120]!r}')

    # 2. DoH 查 www 子域真實 IP（根域會拿到錯 IP）
    real_ip = ''
    try:
        req = urllib.request.Request(
            'https://dns.google/resolve?name=www.xiaohongshu.com&type=A',
            headers={'User-Agent': 'NoteHub/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            dns_data = json.loads(resp.read().decode('utf-8'))
        for a in dns_data.get('Answer', []):
            if a.get('type') == 1 and a.get('data'):
                real_ip = a['data']
                break
    except Exception as e:
        raise ValueError(f'小紅書 DoH 查 IP 失敗: {e}')
    if not real_ip:
        raise ValueError('小紅書 DoH 查 IP 為空')

    # 3. curl --resolve 繞 DNS 污染抓頁面
    host = 'www.xiaohongshu.com'
    try:
        r2 = subprocess.run(
            ['curl', '-s', '-A', _XHS_UA, '-k', '--max-time', '20',
             '--resolve', f'{host}:443:{real_ip}', resolved],
            capture_output=True, text=True, timeout=30)
        html = r2.stdout
    except Exception as e:
        raise ValueError(f'小紅書抓取失敗: {e}')
    if not html or '此網域已經遭到封鎖' in html:
        raise ValueError('小紅書回傳封鎖頁或空頁')

    # 4. 解析 __INITIAL_STATE__（大括號平衡 + undefined→null）
    title = desc = ''
    tags = []
    start = html.find('window.__INITIAL_STATE__=')
    if start != -1:
        i = html.find('{', start)
        depth = 0
        in_str = False
        esc = False
        json_str = ''
        for j in range(i, len(html)):
            c = html[j]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        json_str = html[i:j + 1]
                        break
        if json_str:
            json_str = re.sub(r':undefined\b', ':null', json_str)
            json_str = re.sub(r'undefined\b', 'null', json_str)
            try:
                state = json.loads(json_str)
                note = ((state.get('noteData') or {}).get('data') or {}).get('noteData') or {}
                title = (note.get('title') or '').strip()
                desc = (note.get('desc') or '').strip()
                tag_list = note.get('tagList') or []
                tags = [t.get('name', '').strip() for t in tag_list
                        if t.get('name') and t.get('name').strip()]
            except Exception as e:
                print(f'[url] xhs __INITIAL_STATE__ parse failed: {e}', file=sys.stderr)

    parts = [f'標題：{title}']
    if desc:
        parts.append(desc)
    if tags:
        parts.append(f'標籤：{"、".join(tags[:8])}')
    text = '\n'.join(parts).strip()
    if len(text) < 10:
        raise ValueError('小紅書內容解析為空（可能需登入）')
    return text


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
        # 2026-08-05：小紅書走專用路徑（DoH 繞 DNS 污染），urllib 直接抓會 SSL 失敗
        if _is_xhs_url(input_path):
            text = _fetch_xhs(input_path)
            title = text.split('\n', 1)[0].replace('標題：', '', 1)[:200] if text else input_path
            url_hash = hashlib.md5(input_path.encode()).hexdigest()[:12]
            return ExtractResult(
                text=text,
                metadata={
                    "title": title,
                    "url": input_path,
                    "fetched_chars": len(text),
                },
                source_type="url",
                source_id=url_hash,
            )
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
