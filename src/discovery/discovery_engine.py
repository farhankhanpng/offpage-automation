"""Opportunity Discovery Engine: public RSS feeds, GDELT and seed URLs.

Feed and GDELT items are pre-filtered on their headline/summary: only items that
mention a tracked brand, a tracked competitor or a coworking/CRE term are kept,
so the pipeline doesn't download (and score) every unrelated startup story.
Seed URLs are always kept.
"""

import time
from typing import Any, Dict, List, Optional

from ..scoring.opportunity_scorer import RELEVANT_CRE_KEYWORDS
from ..utils.logger import get_logger
from ..utils.text_match import matching_phrases
from ..utils.time_utils import now_ist_str
from ..utils.url_utils import extract_domain, generate_stable_id, normalize_url
from .gdelt_client import GDELTClient
from .rss_parser import RSSFeedParser

logger = get_logger("DiscoveryEngine")

GDELT_MIN_INTERVAL_SECONDS = 5.0  # GDELT asks clients to stay under one request per 5 seconds


class DiscoveryEngine:
    def __init__(self, config: Dict[str, Any], health=None, relevance_terms: Optional[List[str]] = None):
        self.config = config
        crawler_cfg = config.get("crawler", {})
        self.user_agent = crawler_cfg.get("user_agent", "IASpaces-OffPage-Bot/1.0 (+https://iaspaces.co)")
        self.timeout = crawler_cfg.get("timeout_seconds", 15)
        self.health = health
        self.relevance_terms = list(relevance_terms or []) + RELEVANT_CRE_KEYWORDS
        self.rss_parser = RSSFeedParser(user_agent=self.user_agent, timeout=self.timeout)
        self.gdelt_client = GDELTClient(user_agent=self.user_agent, timeout=self.timeout)
        self.stats = {"feed_items": 0, "kept_after_filter": 0}

    def _record(self, source: str, ok: bool, url: str = "", detail: str = ""):
        if self.health is not None:
            self.health.record(source, ok, url=url, detail=detail)

    def is_relevant(self, item: Dict[str, Any]) -> bool:
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        return bool(matching_phrases(text, self.relevance_terms))

    def _add(self, discovered: Dict[str, Dict[str, Any]], items: List[Dict[str, Any]]):
        for item in items:
            self.stats["feed_items"] += 1
            if not self.is_relevant(item):
                continue
            norm = item.get("url")
            if norm and norm not in discovered:
                self.stats["kept_after_filter"] += 1
                discovered[norm] = item

    def run_discovery(
        self,
        custom_rss_feeds: Optional[List[Any]] = None,
        gdelt_queries: Optional[List[str]] = None,
        seed_urls: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        discovered: Dict[str, Dict[str, Any]] = {}

        for feed in custom_rss_feeds or []:
            if isinstance(feed, dict):
                feed_url, label = feed.get("url", "").strip(), feed.get("name", "Public RSS")
            else:
                feed_url, label = str(feed).strip(), f"RSS ({extract_domain(str(feed))})"
            if not feed_url.startswith(("http://", "https://")):
                continue
            logger.info(f"Checking feed: {label} ({feed_url})")
            items = self.rss_parser.fetch_and_parse(feed_url, source_label=label)
            self._record("rss feed", items is not None, feed_url, "" if items is not None else "feed fetch failed")
            self._add(discovered, items or [])

        last_gdelt = 0.0
        for q in gdelt_queries or []:
            wait = GDELT_MIN_INTERVAL_SECONDS - (time.time() - last_gdelt)
            if last_gdelt and wait > 0:
                time.sleep(wait)
            logger.info(f"Checking GDELT query: {q}")
            items = self.gdelt_client.search(q, max_records=25)
            last_gdelt = time.time()
            self._record("gdelt query", items is not None, q, "" if items is not None else "GDELT request failed")
            self._add(discovered, items or [])

        for seed in seed_urls or []:
            raw_url = (seed.get("source_url") if isinstance(seed, dict) else str(seed)) or ""
            norm = normalize_url(raw_url.strip())
            if norm and norm not in discovered:
                discovered[norm] = {
                    "url": norm,
                    "raw_url": raw_url,
                    "title": (seed.get("title") if isinstance(seed, dict) else "") or "",
                    "summary": "",
                    "published_date": "",
                    "domain": extract_domain(norm),
                    "source": "Seed List",
                    "discovery_date": now_ist_str(),
                }

        results = []
        for norm_url, data in discovered.items():
            record = dict(data)
            record["id"] = generate_stable_id(norm_url, prefix="OPP")
            results.append(record)

        logger.info(
            f"Discovery completed: {len(results)} candidates "
            f"({self.stats['kept_after_filter']} of {self.stats['feed_items']} feed items passed the relevance filter)."
        )
        return results
