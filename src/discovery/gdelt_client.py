"""GDELT 2.0 Doc API public search client for commercial real estate & coworking news.
GDELT 2.0 is 100% free and requires no API key.
"""

import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional

from ..utils.logger import get_logger
from ..utils.time_utils import now_ist_str
from ..utils.url_utils import normalize_url, extract_domain

logger = get_logger("GDELTClient")


class GDELTClient:
    """Queries GDELT 2.0 public document API for fresh Indian startup and workspace news."""

    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(self, user_agent: str = "IASpaces-OffPage-Bot/1.0", timeout: int = 15):
        self.user_agent = user_agent
        self.timeout = timeout

    def build_query_url(self, query: str, max_records: int = 30) -> str:
        params = {
            "query": f"{query} sourcecountry:IN",
            "mode": "ArtList",
            "maxrecords": str(max_records),
            "format": "json",
            "sort": "DateDesc"
        }
        return f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

    def search(self, query: str, max_records: int = 30) -> Optional[List[Dict[str, Any]]]:
        """Search GDELT public news API. Returns None when the request failed."""
        url = self.build_query_url(query, max_records=max_records)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            logger.warning(f"GDELT search failed for '{query}': {e}")
            return None

        articles = data.get("articles", [])
        results: List[Dict[str, Any]] = []

        for art in articles:
            raw_url = art.get("url", "")
            norm_url = normalize_url(raw_url)
            if not norm_url:
                continue

            results.append({
                "url": norm_url,
                "raw_url": raw_url,
                "title": art.get("title", ""),
                "summary": "",
                "published_date": art.get("seendate", ""),
                "domain": extract_domain(norm_url) or art.get("domain", ""),
                "source": "GDELT",
                "discovery_date": now_ist_str()
            })

        return results
