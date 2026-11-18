"""Competitor Opportunity Tracker.

Detects coverage of the competitors listed in config/competitors.yaml (whole-word
name match or an outbound link to their domain) and suggests an editorial angle.
Only pages that were actually fetched and inspected produce rows.
"""

from typing import Any, Dict, List, Optional

from ..utils.html_parser import find_mention_context, parse_html_content
from ..utils.logger import get_logger
from ..utils.text_match import contains_phrase, matching_phrases
from ..utils.time_utils import now_ist_str
from ..utils.url_utils import extract_domain, generate_stable_id, normalize_url

logger = get_logger("CompetitorTracker")

DEFAULT_COMPETITORS = [
    {"name": "Awfis", "domain": "awfis.com"},
    {"name": "Smartworks", "domain": "smartworksoffice.com"},
    {"name": "Innov8", "domain": "innov8.work"},
    {"name": "IndiQube", "domain": "indiqube.com"},
    {"name": "WeWork India", "domain": "wework.co.in"},
]

LISTICLE_WORDS = ["best", "top", "list", "options", "guide", "comparison", "alternatives"]
TIER2_WORDS = ["tier-2", "tier 2", "tier-3", "tier ii", "smaller cities", "indore", "jaipur", "surat", "vadodara", "chandigarh"]
MARKET_WORDS = ["funding", "ipo", "lease", "leasing", "expansion", "revenue", "report"]
ENTERPRISE_WORDS = ["managed office", "enterprise", "bespoke", "gcc", "global capability"]


def competitors_from_config(config: Dict[str, Any]) -> List[Dict[str, str]]:
    items = (config or {}).get("competitors") or []
    out = [{"name": c.get("name", ""), "domain": c.get("domain", "")} for c in items if c.get("name")]
    return out or DEFAULT_COMPETITORS


class CompetitorTracker:
    def __init__(self, competitors: Optional[List[Dict[str, str]]] = None):
        self.competitors = competitors or DEFAULT_COMPETITORS

    @staticmethod
    def editorial_angle(title: str, body: str) -> str:
        title_l = title.lower()
        lead = body[:3000]
        if matching_phrases(title_l, LISTICLE_WORDS):
            return "Listicle Inclusion / Resource Update"
        if matching_phrases(f"{title_l} {lead}", TIER2_WORDS):
            return "Tier-2 Coworking Expansion / Decentralization Narrative"
        if matching_phrases(f"{title_l} {lead}", ENTERPRISE_WORDS):
            return "Managed Enterprise Office Solutions Angle"
        if matching_phrases(f"{title_l} {lead}", MARKET_WORDS):
            return "Industry Commentary / Market Trends Quote"
        return "General Market Commentary"

    def analyze_page_for_competitors(self, url: str, html: str, page_title: str = "") -> List[Dict[str, Any]]:
        parsed = parse_html_content(html, base_url=url)
        body_text = parsed.get("body_text", "")
        title = page_title or parsed.get("title", "")
        links = parsed.get("links", [])
        domain = extract_domain(url)
        now_str = now_ist_str()
        angle = self.editorial_angle(title, body_text)

        rows: List[Dict[str, Any]] = []
        for comp in self.competitors:
            name = comp["name"]
            comp_domain = (comp.get("domain") or "").lower()
            if comp_domain and domain.endswith(comp_domain):
                continue  # a competitor's own site is not an outreach target
            mentioned = contains_phrase(title, name) or contains_phrase(body_text, name)
            comp_links = [lk for lk in links if comp_domain and extract_domain(lk.get("href", "")).endswith(comp_domain)]
            if not (mentioned or comp_links):
                continue
            rows.append({
                "id": generate_stable_id(f"{url}::{name}", prefix="COMP"),
                "publication": domain,
                "competitor": name,
                "source_url": normalize_url(url),
                "page_title": title,
                "competitor_linked": "Yes" if comp_links else "No",
                "competitor_link_url": comp_links[0]["href"] if comp_links else "",
                "evidence": ((find_mention_context(parsed.get("main_text", ""), name, window=140)
                              or find_mention_context(body_text, name, window=140)) if mentioned else "")
                            or f"Outbound link to {comp_domain}",
                "editorial_angle": angle,
                "discovery_date": now_str,
            })
        return rows
