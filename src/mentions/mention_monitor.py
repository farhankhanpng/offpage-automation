"""Brand Mention Monitor for tracking IA Spaces, India Accelerator, and MySOHO coverage.
Inspects fetched HTML to verify whether brand mentions include a hyperlink to iaspaces.co.
"""

import urllib.request
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger
from ..utils.url_utils import normalize_url, extract_domain, generate_stable_id
from ..utils.html_parser import parse_html_content, find_mention_context
from ..utils.rate_limiter import PoliteRateLimiter

logger = get_logger("MentionMonitor")

DEFAULT_BRANDS = [
    "IA Spaces",
    "India Accelerator",
    "India Accelerator Coworking",
    "MySOHO"
]

TARGET_DOMAINS = ["iaspaces.co", "www.iaspaces.co"]


class MentionMonitor:
    """Fetches candidate pages, verifies brand mentions, and determines link status."""

    def __init__(
        self,
        brands: Optional[List[str]] = None,
        target_domains: Optional[List[str]] = None,
        rate_limiter: Optional[PoliteRateLimiter] = None,
        user_agent: str = "IASpaces-OffPage-Bot/1.0",
        timeout: int = 15
    ):
        self.brands = brands or DEFAULT_BRANDS
        self.target_domains = target_domains or TARGET_DOMAINS
        self.rate_limiter = rate_limiter or PoliteRateLimiter(default_delay=2.0, user_agent=user_agent)
        self.user_agent = user_agent
        self.timeout = timeout

    def fetch_page(self, url: str) -> Dict[str, Any]:
        """Politely fetch HTML of target page respecting rate limits."""
        self.rate_limiter.wait_if_needed(url)
        if not self.rate_limiter.is_allowed_by_robots(url):
            return {"status": "Blocked by robots.txt", "html": "", "http_code": 403}

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                html = resp.read().decode("utf-8", errors="replace")
                return {"status": "Success", "html": html, "http_code": status_code, "final_url": resp.geturl()}
        except Exception as e:
            logger.warning(f"Error fetching page {url}: {e}")
            return {"status": f"Fetch Error: {str(e)[:100]}", "html": "", "http_code": 0}

    def inspect_content(self, url: str, html: str, source_label: str = "Manual") -> List[Dict[str, Any]]:
        """Inspect HTML content for brand mentions and outgoing links to IA Spaces."""
        parsed = parse_html_content(html, base_url=url)
        body_text = parsed.get("body_text", "")
        title = parsed.get("title", "")
        domain = extract_domain(url)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Find all links pointing to target domain
        ia_links = []
        for link in parsed.get("links", []):
            dest = link.get("href", "")
            dest_domain = extract_domain(dest)
            if dest_domain in self.target_domains:
                ia_links.append(link)

        mentions_found: List[Dict[str, Any]] = []

        # Check each tracked brand
        for brand in self.brands:
            if brand.lower() in body_text.lower() or brand.lower() in title.lower():
                context = find_mention_context(body_text, brand, window=120)
                has_link = len(ia_links) > 0
                link_destination = ia_links[0]["href"] if has_link else ""
                anchor_text = ia_links[0].get("anchor_text", "") if has_link else ""

                mention_record = {
                    "id": generate_stable_id(f"{url}::{brand}", prefix="MEN"),
                    "brand": brand,
                    "url": normalize_url(url),
                    "title": title or "Untitled Page",
                    "domain": domain,
                    "discovery_date": now_str,
                    "context": context,
                    "has_hyperlink": "Yes" if has_link else "No",
                    "link_destination": link_destination,
                    "anchor_text": anchor_text,
                    "verification_status": "Verified (Live Page)",
                    "source": source_label,
                    "is_unlinked": not has_link
                }
                mentions_found.append(mention_record)

        return mentions_found

    def analyze_url(self, url: str, source_label: str = "Web") -> List[Dict[str, Any]]:
        """Fetch URL and perform mention inspection."""
        fetch_result = self.fetch_page(url)
        if fetch_result.get("status") != "Success":
            # Cannot label unlinked without inspecting page
            return [{
                "id": generate_stable_id(f"{url}::ERROR", prefix="MEN"),
                "brand": "N/A",
                "url": normalize_url(url),
                "title": "",
                "domain": extract_domain(url),
                "discovery_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "context": "",
                "has_hyperlink": "Unknown",
                "link_destination": "",
                "anchor_text": "",
                "verification_status": f"Fetch Failed: {fetch_result.get('status')}",
                "source": source_label,
                "is_unlinked": False
            }]

        return self.inspect_content(url, fetch_result["html"], source_label=source_label)
