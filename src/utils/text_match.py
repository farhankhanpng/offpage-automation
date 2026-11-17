"""Whole-word text matching and contact detection helpers.

Substring matching caused false positives: "IA Spaces" matched "India spaces",
"cre" matched "create"/"credit", "india" matched "indian". These helpers match
whole words/phrases only (case-insensitive).
"""

import re
from functools import lru_cache
from typing import Iterable, List
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@lru_cache(maxsize=512)
def _phrase_regex(phrase: str) -> "re.Pattern":
    escaped = re.escape(phrase.strip())
    # \b only works next to word characters; use look-arounds so phrases ending in
    # punctuation (e.g. "iaspaces.co") still match as a whole token.
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.IGNORECASE)


def contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return bool(_phrase_regex(phrase).search(text))


def find_phrase(text: str, phrase: str):
    """Return the first regex match for phrase in text (or None)."""
    if not text or not phrase:
        return None
    return _phrase_regex(phrase).search(text)


def matching_phrases(text: str, phrases: Iterable[str]) -> List[str]:
    return [p for p in phrases if contains_phrase(text, p)]


def find_contact_emails(html: str, page_url: str = "") -> List[str]:
    """Emails published on the page itself (mailto: links first, then visible text).

    Only addresses on the page's own domain (or its parent domain) are returned, so we
    never attribute a random third-party address to a publication.
    """
    if not html:
        return []
    host = urlparse(page_url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    root = ".".join(host.split(".")[-2:]) if host else ""

    found: List[str] = []
    for m in re.finditer(r'mailto:([^"\'?>\s]+)', html, re.IGNORECASE):
        found.append(m.group(1).strip().lower())
    for m in EMAIL_RE.finditer(html):
        found.append(m.group(0).strip().lower())

    result: List[str] = []
    for email in found:
        domain = email.rsplit("@", 1)[-1]
        if root and not (domain == root or domain.endswith("." + root) or domain == host):
            continue
        if any(email.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            continue
        if email not in result:
            result.append(email)
    return result
