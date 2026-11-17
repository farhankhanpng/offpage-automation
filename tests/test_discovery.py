"""Tests for discovery relevance filtering and failure reporting."""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.discovery.discovery_engine import DiscoveryEngine  # noqa: E402
from src.utils.health import RunHealth  # noqa: E402


class StubRSS:
    def __init__(self, items):
        self.items = items

    def fetch_and_parse(self, url, source_label="RSS"):
        return self.items


class TestDiscovery(unittest.TestCase):

    def test_only_relevant_feed_items_are_kept(self):
        engine = DiscoveryEngine({}, relevance_terms=["IA Spaces", "Awfis"])
        engine.rss_parser = StubRSS([
            {"url": "https://inc42.com/a", "title": "Awfis posts record quarter", "summary": ""},
            {"url": "https://inc42.com/b", "title": "Fintech startup raises funding to create credit app", "summary": ""},
            {"url": "https://inc42.com/c", "title": "Why managed office demand is rising", "summary": ""},
        ])
        out = engine.run_discovery(custom_rss_feeds=["https://inc42.com/feed/"])
        self.assertEqual(sorted(o["url"] for o in out), ["https://inc42.com/a", "https://inc42.com/c"])
        self.assertTrue(all(o["id"].startswith("OPP-") for o in out))

    def test_failed_feed_is_recorded(self):
        health = RunHealth()
        engine = DiscoveryEngine({}, health=health)
        engine.rss_parser = StubRSS(None)
        engine.run_discovery(custom_rss_feeds=["https://inc42.com/feed/"])
        self.assertEqual(health.sources["rss feed"], {"attempted": 1, "succeeded": 0})

    def test_seed_urls_are_always_kept(self):
        out = DiscoveryEngine({}).run_discovery(seed_urls=[{"source_url": "https://example.com/x?utm_source=a", "title": "T"}])
        self.assertEqual(out[0]["url"], "https://example.com/x")
        self.assertEqual(out[0]["title"], "T")


if __name__ == "__main__":
    unittest.main()
