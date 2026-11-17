"""Backlink Monitor for verifying known backlink source pages.
Checks HTTP status, link presence, anchor text, and rel attributes (nofollow, sponsored, ugc).
"""

import urllib.request
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger
from ..utils.url_utils import normalize_url, extract_domain, generate_stable_id
from ..utils.html_parser import parse_html_content
from ..utils.rate_limiter import PoliteRateLimiter

logger = get_logger("BacklinkMonitor")

TARGET_DOMAINS = ["iaspaces.co", "www.iaspaces.co"]


class BacklinkMonitor:
    """Verifies backlink health on designated source pages."""

    def __init__(
        self,
        target_domains: Optional[List[str]] = None,
        rate_limiter: Optional[PoliteRateLimiter] = None,
        user_agent: str = "IASpaces-OffPage-Bot/1.0",
        timeout: int = 15
    ):
        self.target_domains = target_domains or TARGET_DOMAINS
        self.rate_limiter = rate_limiter or PoliteRateLimiter(default_delay=2.0, user_agent=user_agent)
        self.user_agent = user_agent
        self.timeout = timeout

    def check_source_page(self, source_url: str, expected_target: Optional[str] = None) -> Dict[str, Any]:
        """Fetch source page and check if a link to IA Spaces is active."""
        norm_source = normalize_url(source_url)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record: Dict[str, Any] = {
            "id": generate_stable_id(norm_source, prefix="BL"),
            "source_url": norm_source,
            "target_url": expected_target or "https://iaspaces.co",
            "http_status": 0,
            "link_exists": "No",
            "anchor_text": "",
            "rel_attributes": "",
            "last_checked": now_str,
            "link_status": "Not Checked",
            "notes": ""
        }

        self.rate_limiter.wait_if_needed(norm_source)
        if not self.rate_limiter.is_allowed_by_robots(norm_source):
            record["link_status"] = "Blocked by robots.txt"
            record["notes"] = "Robots.txt disallows automated checking"
            return record

        req = urllib.request.Request(
            norm_source,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                final_url = resp.geturl()
                html = resp.read().decode("utf-8", errors="replace")
                record["http_status"] = status_code

                if normalize_url(final_url) != norm_source:
                    record["notes"] = f"Source redirected to {final_url}"
        except urllib.error.HTTPError as e:
            record["http_status"] = e.code
            record["link_status"] = "Error"
            record["notes"] = f"HTTP Error: {e.code}"
            return record
        except Exception as e:
            record["link_status"] = "Error"
            record["notes"] = f"Connection error: {str(e)[:100]}"
            return record

        parsed = parse_html_content(html, base_url=norm_source)
        found_links = []

        for lk in parsed.get("links", []):
            href = lk.get("href", "")
            domain = extract_domain(href)
            if domain in self.target_domains:
                found_links.append(lk)

        if not found_links:
            record["link_exists"] = "No"
            record["link_status"] = "Missing"
            record["notes"] = "Page fetched successfully (200 OK) but no link to iaspaces.co found."
            return record

        # Link exists! Check first matching link or target match
        best_match = found_links[0]
        if expected_target:
            norm_expected = normalize_url(expected_target)
            for fl in found_links:
                if normalize_url(fl.get("href", "")) == norm_expected:
                    best_match = fl
                    break

        record["link_exists"] = "Yes"
        record["target_url"] = best_match.get("href", "")
        record["anchor_text"] = best_match.get("anchor_text", "")
        record["rel_attributes"] = best_match.get("rel", "") or "dofollow"

        # Categorize status
        rel_lower = record["rel_attributes"].lower()
        if "nofollow" in rel_lower or "sponsored" in rel_lower or "ugc" in rel_lower:
            record["link_status"] = "Live (Nofollow/Sponsored/UGC)"
        else:
            record["link_status"] = "Live (Dofollow)"

        record["notes"] = f"Verified active link with anchor '{record['anchor_text']}'"
        return record

    def audit_backlink_list(self, backlinks: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Audit a batch of backlink sources."""
        results = []
        for item in backlinks:
            source = item.get("source_url", "")
            target = item.get("target_url", "")
            if not source:
                continue
            logger.info(f"Auditing backlink source: {source}")
            res = self.check_source_page(source, expected_target=target)
            results.append(res)
        return results
