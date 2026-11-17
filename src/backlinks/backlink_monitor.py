"""Backlink Monitor: verifies known backlink source pages.

Checks HTTP status, link presence, anchor text and rel attributes (nofollow, sponsored, ugc).
A page that could not be fetched is reported as "Could Not Verify", never as "Missing".
Links that point to a legacy page instead of iaspaces.co (for example
indiaaccelerator.co/ia-spaces/) are called out in Notes.
"""

from typing import Any, Dict, List, Optional

from ..utils.fetcher import PoliteFetcher
from ..utils.html_parser import parse_html_content
from ..utils.logger import get_logger
from ..utils.time_utils import now_ist_str
from ..utils.url_utils import extract_domain, generate_stable_id, normalize_url

logger = get_logger("BacklinkMonitor")

TARGET_DOMAINS = ["iaspaces.co", "www.iaspaces.co"]
DEFAULT_LEGACY_TARGETS = ["indiaaccelerator.co/ia-spaces", "indiaaccelerator.co/coworking", "indiaaccelerator.co/spaces"]


class BacklinkMonitor:
    def __init__(
        self,
        target_domains: Optional[List[str]] = None,
        fetcher: Optional[PoliteFetcher] = None,
        legacy_targets: Optional[List[str]] = None,
        user_agent: str = "IASpaces-OffPage-Bot/1.0 (+https://iaspaces.co)",
        timeout: int = 15,
    ):
        self.target_domains = [d.lower() for d in (target_domains or TARGET_DOMAINS)]
        self.legacy_targets = [t.lower() for t in (legacy_targets or DEFAULT_LEGACY_TARGETS)]
        self.fetcher = fetcher or PoliteFetcher(user_agent=user_agent, timeout=timeout)

    def _legacy_links(self, links: List[Dict[str, str]]) -> List[Dict[str, str]]:
        out = []
        for lk in links:
            href = normalize_url(lk.get("href", "")).lower().replace("://www.", "://")
            if any(t in href for t in self.legacy_targets):
                out.append(lk)
        return out

    def check_source_page(self, source_url: str, expected_target: Optional[str] = None) -> Dict[str, Any]:
        norm_source = normalize_url(source_url)
        record: Dict[str, Any] = {
            "id": generate_stable_id(norm_source, prefix="BL"),
            "source_url": norm_source,
            "target_url": expected_target or "https://iaspaces.co",
            "http_status": 0,
            "link_exists": "Unknown",
            "anchor_text": "",
            "rel_attributes": "",
            "last_checked": now_ist_str(),
            "link_status": "Could Not Verify",
            "notes": "",
        }

        res = self.fetcher.fetch(norm_source, source="backlink check")
        record["http_status"] = res.get("http_code", 0)
        if not res.get("ok"):
            record["notes"] = f"Could not fetch page: {res.get('status')} {res.get('error', '')}".strip()
            return record

        notes = []
        if normalize_url(res.get("final_url", "")) not in ("", norm_source):
            notes.append(f"Source redirected to {res['final_url']}")

        parsed = parse_html_content(res["html"], base_url=res.get("final_url") or norm_source)
        links = parsed.get("links", [])
        found = [lk for lk in links if extract_domain(lk.get("href", "")) in self.target_domains]

        if not found:
            record["link_exists"] = "No"
            record["link_status"] = "Missing"
            legacy = self._legacy_links(links)
            if legacy:
                notes.append(
                    f"Links to legacy page {legacy[0].get('href')} (anchor '{legacy[0].get('anchor_text', '')}') "
                    f"instead of iaspaces.co - update the link or 301-redirect that page"
                )
            else:
                notes.append("Page fetched but no link to iaspaces.co found.")
            record["notes"] = "; ".join(notes)
            return record

        best = found[0]
        if expected_target:
            want = normalize_url(expected_target)
            best = next((lk for lk in found if normalize_url(lk.get("href", "")) == want), best)

        rel = (best.get("rel") or "").strip()
        record.update(
            link_exists="Yes",
            target_url=best.get("href", ""),
            anchor_text=best.get("anchor_text", ""),
            rel_attributes=rel or "(none - followed)",
        )
        rel_lower = rel.lower()
        if any(x in rel_lower for x in ("nofollow", "sponsored", "ugc")):
            record["link_status"] = "Live (Nofollow/Sponsored/UGC)"
        else:
            record["link_status"] = "Live (Followed)"
        notes.append(f"Verified link with anchor '{record['anchor_text']}'")
        record["notes"] = "; ".join(notes)
        return record

    def audit_backlink_list(self, backlinks: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results = []
        for item in backlinks:
            source = (item.get("source_url") or "").strip()
            if not source:
                continue
            logger.info(f"Auditing backlink source: {source}")
            results.append(self.check_source_page(source, expected_target=(item.get("target_url") or "").strip() or None))
        return results
