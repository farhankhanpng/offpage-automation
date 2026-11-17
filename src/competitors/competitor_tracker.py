"""Competitor Opportunity Tracker for identifying genuine editorial gaps.
Analyzes coverage of Awfis, Smartworks, Innov8, IndiQube, and WeWork India.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger
from ..utils.url_utils import normalize_url, extract_domain, generate_stable_id
from ..utils.html_parser import parse_html_content, find_mention_context

logger = get_logger("CompetitorTracker")

DEFAULT_COMPETITORS = [
    {"name": "Awfis", "domain": "awfis.com"},
    {"name": "Smartworks", "domain": "smartworksoffice.com"},
    {"name": "Innov8", "domain": "innov8.work"},
    {"name": "IndiQube", "domain": "indiqube.com"},
    {"name": "WeWork India", "domain": "wework.co.in"}
]


class CompetitorTracker:
    """Tracks competitor media appearances and identifies editorial outreach angles."""

    def __init__(self, competitors: Optional[List[Dict[str, str]]] = None):
        self.competitors = competitors or DEFAULT_COMPETITORS

    def analyze_page_for_competitors(self, url: str, html: str, page_title: str = "") -> List[Dict[str, Any]]:
        """Inspect HTML to detect competitor mentions, links, and strategic editorial angle."""
        parsed = parse_html_content(html, base_url=url)
        body_text = parsed.get("body_text", "")
        title = page_title or parsed.get("title", "")
        domain = extract_domain(url)
        outgoing_links = parsed.get("links", [])
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        opportunities: List[Dict[str, Any]] = []

        for comp in self.competitors:
            comp_name = comp["name"]
            comp_domain = comp.get("domain", "").lower()

            name_mentioned = comp_name.lower() in body_text.lower() or comp_name.lower() in title.lower()

            # Check if competitor has outgoing link
            comp_links = []
            for lk in outgoing_links:
                href_domain = extract_domain(lk.get("href", ""))
                if comp_domain and comp_domain in href_domain:
                    comp_links.append(lk)

            has_link = len(comp_links) > 0

            if name_mentioned or has_link:
                context = find_mention_context(body_text, comp_name, window=140) if name_mentioned else ""

                # Determine editorial angle
                angle = "General Market Commentary"
                title_lower = title.lower()
                body_lower = body_text.lower()

                if any(k in title_lower or k in body_lower for k in ["best", "top", "list", "options", "places"]):
                    angle = "Listicle Inclusion / Resource Update"
                elif any(k in title_lower or k in body_lower for k in ["tier-2", "tier 2", "tier-3", "smaller cities", "indore", "jaipur"]):
                    angle = "Tier-2 Coworking Expansion / Decentralization Narrative"
                elif any(k in title_lower or k in body_lower for k in ["funding", "ipo", "lease", "expansion", "growth"]):
                    angle = "Industry Commentary / Market Trends Quote"
                elif any(k in title_lower or k in body_lower for k in ["managed office", "enterprise", "bespoke"]):
                    angle = "Managed Enterprise Office Solutions Angle"

                # Assess opportunity viability
                opp_record = {
                    "id": generate_stable_id(f"{url}::{comp_name}", prefix="COMP"),
                    "publication": domain,
                    "competitor": comp_name,
                    "source_url": normalize_url(url),
                    "page_title": title,
                    "competitor_linked": "Yes" if has_link else "No",
                    "competitor_link_url": comp_links[0]["href"] if has_link else "",
                    "evidence": context or f"Detected competitor domain {comp_domain} in outbound links",
                    "editorial_angle": angle,
                    "discovery_date": now_str
                }
                opportunities.append(opp_record)

        return opportunities
