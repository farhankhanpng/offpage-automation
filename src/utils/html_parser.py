"""HTML parser utility using standard library html.parser with BeautifulSoup fallback.
Extracts page title, meta description, links, anchor texts, and clean body text.
"""

import re
from html.parser import HTMLParser
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin


class StandardHTMLParser(HTMLParser):
    """Robust HTML parser extracting metadata, links, and text content."""

    def __init__(self, base_url: str = ""):
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.meta_description = ""
        self.canonical = ""
        self.links: List[Dict[str, str]] = []
        self.text_chunks: List[str] = []

        self._in_title = False
        self._in_script = False
        self._in_style = False
        self._current_a: Optional[Dict[str, str]] = None
        self._current_a_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        tag = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "title":
            self._in_title = True
        elif tag in ("script", "style", "noscript"):
            self._in_script = True
        elif tag == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "")
            if name == "description" or prop == "og:description":
                if not self.meta_description:
                    self.meta_description = content.strip()
        elif tag == "link":
            rel = attr_dict.get("rel", "").lower()
            if rel == "canonical":
                self.canonical = attr_dict.get("href", "").strip()
        elif tag == "a":
            href = attr_dict.get("href", "").strip()
            rel = attr_dict.get("rel", "").strip()
            resolved_href = urljoin(self.base_url, href) if (self.base_url and href) else href
            self._current_a = {
                "raw_href": href,
                "href": resolved_href,
                "rel": rel,
                "target": attr_dict.get("target", "").strip()
            }
            self._current_a_text = []

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "noscript"):
            self._in_script = False
        elif tag == "a" and self._current_a is not None:
            anchor_text = " ".join("".join(self._current_a_text).split())
            self._current_a["anchor_text"] = anchor_text
            self.links.append(self._current_a)
            self._current_a = None
            self._current_a_text = []

    def handle_data(self, data: str):
        if self._in_script or self._in_style:
            return
        if self._in_title:
            self.title += data
        if self._current_a is not None:
            self._current_a_text.append(data)
        stripped = data.strip()
        if stripped:
            self.text_chunks.append(stripped)


def parse_html_content(html: str, base_url: str = "") -> Dict[str, Any]:
    """Parse HTML string and return extracted title, meta, links, and body text."""
    if not html:
        return {
            "title": "",
            "meta_description": "",
            "canonical": "",
            "links": [],
            "body_text": "",
            "main_text": "",
        }

    # Attempt BeautifulSoup if installed
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = (soup.title.string or "").strip() if soup.title else ""
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)}) or \
                   soup.find("meta", attrs={"property": re.compile(r"^og:description$", re.I)})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].strip()

        canonical = ""
        can_tag = soup.find("link", rel=lambda val: val and "canonical" in val.lower())
        if can_tag and can_tag.get("href"):
            canonical = can_tag["href"].strip()

        links = []
        for a in soup.find_all("a", href=True):
            raw_href = a["href"].strip()
            resolved = urljoin(base_url, raw_href) if base_url else raw_href
            rel = " ".join(a["rel"]) if isinstance(a.get("rel"), list) else (a.get("rel") or "")
            links.append({
                "raw_href": raw_href,
                "href": resolved,
                "anchor_text": " ".join(a.get_text(" ").split()),
                "rel": rel,
                "target": a.get("target", "")
            })

        # Separator " " stops words in adjacent tags running together ("StoryIA Spaces")
        body_text = " ".join((soup.body or soup).get_text(" ").split())

        # Article text only: paragraphs, list items and sub-headings outside the site's
        # navigation, header and footer. Used for mention snippets, so a snippet shows the
        # sentence that names the brand rather than the menu.
        container = soup.find("article") or soup.find("main") or soup.body or soup
        blocks = []
        for el in container.find_all(["p", "li", "h2", "h3", "blockquote", "td"]):
            if el.find_parent(["nav", "header", "footer", "aside"]):
                continue
            text = " ".join(el.get_text(" ").split())
            if len(text) >= 25:
                blocks.append(text)
        main_text = " ".join(blocks)
        return {
            "title": title,
            "meta_description": meta_desc,
            "canonical": canonical,
            "links": links,
            "body_text": body_text,
            "main_text": main_text,
        }
    except ImportError:
        pass

    # Standard library fallback
    parser = StandardHTMLParser(base_url=base_url)
    try:
        parser.feed(html)
    except Exception:
        pass

    return {
        "title": " ".join(parser.title.split()),
        "meta_description": parser.meta_description,
        "canonical": parser.canonical,
        "links": parser.links,
        "body_text": " ".join(parser.text_chunks),
        "main_text": " ".join(parser.text_chunks),
    }


def find_mention_context(text: str, brand_name: str, window: int = 120) -> str:
    """Find surrounding snippet context for a brand mention in text."""
    if not text or not brand_name:
        return ""

    pattern = re.compile(re.escape(brand_name), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return ""

    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    snippet = text[start:end].strip()

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return " ".join(snippet.split())
