"""Check that every quoted phrase is really on the page it's attributed to."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
from html.parser import HTMLParser

from .ledger import LOCK, Study, quote_key
from .text import normalize

UA = "receipts/0.2 (+https://github.com/ry-ops/receipts) quote-checker"


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def page_text(raw: str) -> str:
    """Visible text of an HTML page, or the raw text for anything else."""
    if "<" not in raw[:2000]:
        return raw
    p = _Text()
    p.feed(raw)
    return html.unescape(" ".join(p.parts))


def fetch(url: str, timeout: float = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,text/plain,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, errors="replace")


def context(text: str, needle: str, width: int = 70) -> str:
    t, n = normalize(text), normalize(needle)
    i = t.find(n)
    if i < 0:
        return ""
    return t[max(0, i - width): i + len(n) + width]


def check(s: Study, fetcher=fetch) -> list[dict]:
    pages: dict[str, str | Exception] = {}
    results = []
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for q in s.quotes:
        url, text = q.get("url"), q.get("text")
        if not url or not text:
            continue
        if url not in pages:
            try:
                raw = fetcher(url)
                pages[url] = RuntimeError("blocked by a bot check; verify this one in a browser") if looks_blocked(raw) else page_text(raw)
            except Exception as e:  # noqa: BLE001 - report any fetch failure as-is
                pages[url] = e
        page = pages[url]
        if isinstance(page, Exception):
            r = {"url": url, "text": text, "found": False, "checked_at": now, "error": f"{type(page).__name__}: {page}"}
        else:
            ctx = context(page, text)
            r = {"url": url, "text": text, "found": bool(ctx), "checked_at": now, "context": ctx}
        s.lock[quote_key(q)] = r
        results.append(r)
    (s.root / LOCK).write_text(json.dumps(s.lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return results


_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_BLOCKED = re.compile(r"just a moment|attention required|access denied|are you a robot", re.I)


def looks_blocked(page: str) -> bool:
    """A bot-check page instead of the real one (judged by its title): report it
    as blocked rather than as 'quote not found'."""
    m = _TITLE.search(page[:8000])
    return bool(m and _BLOCKED.search(m.group(1)))
