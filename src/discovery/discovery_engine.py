"""Opportunity Discovery Engine orchestrating RSS, Google Alerts, GDELT, and user feeds.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .rss_parser import RSSFeedParser
from .gdelt_client import GDELTClient
from ..utils.logger import get_logger
from ..utils.url_utils import normalize_url, extract_domain, generate_stable_id

logger = get_logger("DiscoveryEngine")


class DiscoveryEngine:
    """Discovers public article and mention opportunities across multiple free streams."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        crawler_cfg = config.get("crawler", {})
        self.user_agent = crawler_cfg.get("user_agent", "IASpaces-OffPage-Bot/1.0")
        self.timeout = crawler_cfg.get("timeout_seconds", 15)

        self.rss_parser = RSSFeedParser(user_agent=self.user_agent, timeout=self.timeout)
        self.gdelt_client = GDELTClient(user_agent=self.user_agent, timeout=self.timeout)

    def run_discovery(
        self,
        custom_rss_feeds: Optional[List[Dict[str, str]]] = None,
        gdelt_queries: Optional[List[str]] = None,
        seed_urls: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Run all active discovery channels and return deduplicated list of candidate URLs."""
        discovered: Dict[str, Dict[str, Any]] = {}

        # 1. Process configured / user RSS & Google Alerts feeds
        feeds = custom_rss_feeds or []
        for feed in feeds:
            if isinstance(feed, dict):
                feed_url = feed.get("url", "").strip()
                label = feed.get("name", "Public RSS")
            else:
                feed_url = str(feed).strip()
                label = "Public RSS"

            if not feed_url or not feed_url.startswith(("http://", "https://")):
                continue
            logger.info(f"Checking feed: {label} ({feed_url})")
            items = self.rss_parser.fetch_and_parse(feed_url, source_label=label)
            for item in items:
                norm = item["url"]
                if norm and norm not in discovered:
                    discovered[norm] = item

        # 2. Process GDELT queries
        queries = gdelt_queries or []
        for q in queries:
            logger.info(f"Checking GDELT public query: {q}")
            items = self.gdelt_client.search(q, max_records=25)
            for item in items:
                norm = item["url"]
                if norm and norm not in discovered:
                    discovered[norm] = item

        # 3. Process seed URLs provided directly
        seeds = seed_urls or []
        for raw_url in seeds:
            norm = normalize_url(raw_url)
            if norm and norm not in discovered:
                discovered[norm] = {
                    "url": norm,
                    "raw_url": raw_url,
                    "title": "",
                    "summary": "User-supplied seed prospect",
                    "published_date": "",
                    "domain": extract_domain(norm),
                    "source": "Seed List",
                    "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

        # Build finalized records with stable IDs
        results: List[Dict[str, Any]] = []
        for norm_url, data in discovered.items():
            record = dict(data)
            record["id"] = generate_stable_id(norm_url, prefix="OPP")
            results.append(record)

        logger.info(f"Discovery completed: {len(results)} distinct opportunities found.")
        return results
