"""Brand Mention Monitor for IA Spaces, India Accelerator and MySOHO coverage.

Inspects page HTML and classifies each brand mention:
  - "Yes (brand-anchored)"  - a link to iaspaces.co whose anchor text contains the brand;
  - "Yes (elsewhere on page)" - the page links to iaspaces.co, but not from the brand words;
  - "No"                     - no link to iaspaces.co at all (a reclamation target).
Brand names are matched as whole words, so "India spaces" no longer counts as "IA Spaces".

"India Accelerator" is also a startup accelerator and investor, so many of its mentions are
about funding rounds, not coworking. Each mention is therefore marked "pitchable" only when
it is about workspace (IA Spaces and MySOHO always are; India Accelerator only when the page
title or the text around the mention uses workspace words). Link requests are only drafted
for pitchable mentions.
"""

from typing import Any, Dict, List, Optional

from ..utils.fetcher import PoliteFetcher
from ..utils.html_parser import find_mention_context, parse_html_content
from ..utils.logger import get_logger
from ..utils.text_match import contains_phrase
from ..utils.time_utils import now_ist_str
from ..utils.url_utils import extract_domain, generate_stable_id, normalize_url

logger = get_logger("MentionMonitor")

DEFAULT_BRANDS = ["IA Spaces", "India Accelerator", "MySOHO"]
TARGET_DOMAINS = ["iaspaces.co", "www.iaspaces.co"]

# Brands that only ever mean the coworking business
WORKSPACE_BRANDS = {"ia spaces", "iaspaces.co", "mysoho", "india accelerator coworking", "india accelerator spaces"}
# Words that show a mention is about workspace rather than startup investing
WORKSPACE_TERMS = [
    "coworking", "co-working", "cowork", "co-work", "workspace", "workspaces", "work space",
    "office space", "office spaces", "managed office", "managed offices", "flexible office",
    "flex space", "flexible workspace", "desks", "seats", "IA Spaces", "MySOHO",
]
NOT_WORKSPACE_STATUS = "Verified (Live Page) - not about coworking, no link request"


def is_workspace_mention(brand: str, page_title: str, context: str) -> bool:
    """True when this mention is about the coworking business (so iaspaces.co is the right link)."""
    if brand.strip().lower() in WORKSPACE_BRANDS:
        return True
    text = f"{page_title} {context}"
    return any(contains_phrase(text, term) for term in WORKSPACE_TERMS)


class MentionMonitor:
    """Verifies brand mentions on fetched pages and their link status."""

    def __init__(
        self,
        brands: Optional[List[str]] = None,
        target_domains: Optional[List[str]] = None,
        fetcher: Optional[PoliteFetcher] = None,
        user_agent: str = "IASpaces-OffPage-Bot/1.0 (+https://iaspaces.co)",
        timeout: int = 15,
    ):
        self.brands = self._dedupe_brands(brands or DEFAULT_BRANDS)
        self.target_domains = [d.lower() for d in (target_domains or TARGET_DOMAINS)]
        self.fetcher = fetcher or PoliteFetcher(user_agent=user_agent, timeout=timeout)

    @staticmethod
    def _dedupe_brands(brands: List[str]) -> List[str]:
        """Longest first, so 'India Accelerator Coworking' is reported instead of also
        reporting the shorter 'India Accelerator' for the same words."""
        seen, out = set(), []
        for b in sorted({b.strip() for b in brands if b and b.strip()}, key=len, reverse=True):
            if b.lower() not in seen:
                seen.add(b.lower())
                out.append(b)
        return out

    def fetch_page(self, url: str) -> Dict[str, Any]:
        return self.fetcher.fetch(url, source="mention check")

    def inspect_content(self, url: str, html: str, source_label: str = "Manual") -> List[Dict[str, Any]]:
        parsed = parse_html_content(html, base_url=url)
        body_text = parsed.get("body_text", "")
        title = parsed.get("title", "")
        haystack = f"{title} {body_text}"
        domain = extract_domain(url)
        now_str = now_ist_str()

        ia_links = [lk for lk in parsed.get("links", []) if extract_domain(lk.get("href", "")) in self.target_domains]

        mentions: List[Dict[str, Any]] = []
        covered_spans: List[str] = []
        for brand in self.brands:
            if not contains_phrase(haystack, brand):
                continue
            # Skip a shorter brand when every occurrence is inside a longer one already reported
            if any(contains_phrase(longer, brand) and haystack.lower().count(brand.lower()) <= haystack.lower().count(longer.lower())
                   for longer in covered_spans):
                continue
            covered_spans.append(brand)

            anchored = [lk for lk in ia_links if contains_phrase(lk.get("anchor_text", ""), brand)]
            chosen = anchored[0] if anchored else (ia_links[0] if ia_links else None)
            if anchored:
                has_link = "Yes (brand-anchored)"
            elif ia_links:
                has_link = "Yes (elsewhere on page)"
            else:
                has_link = "No"

            context = (find_mention_context(parsed.get("main_text", ""), brand, window=120)
                       or find_mention_context(body_text, brand, window=120))
            # A wider window for the topic check than for the snippet shown in the Sheet
            topic_text = (find_mention_context(parsed.get("main_text", ""), brand, window=250)
                          or find_mention_context(body_text, brand, window=250))
            pitchable = has_link == "No" and is_workspace_mention(brand, title, topic_text)

            mentions.append({
                "id": generate_stable_id(f"{url}::{brand}", prefix="MEN"),
                "brand": brand,
                "mentioned_url": normalize_url(url),
                "url": normalize_url(url),
                "page_title": title or "Untitled Page",
                "domain": domain,
                "discovery_date": now_str,
                "context": context,
                "has_hyperlink": has_link,
                "link_destination": chosen.get("href", "") if chosen else "",
                "anchor_text": chosen.get("anchor_text", "") if chosen else "",
                "verification_status": ("Verified (Live Page)" if has_link != "No" or pitchable
                                        else NOT_WORKSPACE_STATUS),
                "source": source_label,
                "is_unlinked": has_link == "No",
                "pitchable": pitchable,
            })
        return mentions

    def analyze_url(self, url: str, source_label: str = "Web") -> List[Dict[str, Any]]:
        """Fetch url and inspect it. Returns [] when the page could not be fetched
        (the failure is recorded in RunHealth instead of being written as a fake row)."""
        res = self.fetch_page(url)
        if not res.get("ok"):
            return []
        return self.inspect_content(res.get("final_url") or url, res["html"], source_label=source_label)
