"""Unit tests for the Brand Mention Monitor."""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.mentions.mention_monitor import MentionMonitor  # noqa: E402
from src.sheets.sheets_client import SHEET_HEADERS  # noqa: E402


class FailingFetcher:
    health = None

    def fetch(self, url, source="page"):
        return {"ok": False, "status": "HTTP 403", "html": "", "error": "HTTP Error 403"}


class TestMentionMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = MentionMonitor(brands=["IA Spaces", "India Accelerator", "MySOHO"], fetcher=FailingFetcher())

    def test_brand_anchored_link(self):
        html = """<html><body>
            <p>We recently reviewed IA Spaces and their growth across NCR.</p>
            <a href="https://iaspaces.co/gurgaon/">Explore IA Spaces Hubs</a></body></html>"""
        res = self.monitor.inspect_content("https://news.example.com/story", html)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["brand"], "IA Spaces")
        self.assertEqual(res[0]["has_hyperlink"], "Yes (brand-anchored)")
        self.assertFalse(res[0]["is_unlinked"])
        self.assertEqual(res[0]["link_destination"], "https://iaspaces.co/gurgaon/")

    def test_link_elsewhere_on_page(self):
        html = """<html><body><p>IA Spaces opened a centre.</p>
            <footer><a href="https://iaspaces.co/">Partner site</a></footer></body></html>"""
        res = self.monitor.inspect_content("https://news.example.com/story", html)
        self.assertEqual(res[0]["has_hyperlink"], "Yes (elsewhere on page)")
        self.assertFalse(res[0]["is_unlinked"])

    def test_unlinked_mention_detection(self):
        html = "<html><body><p>According to Ashish Bhatia, India Accelerator Coworking is seeing high occupancy.</p></body></html>"
        res = self.monitor.inspect_content("https://tech.example.com/coworking", html)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["brand"], "India Accelerator")
        self.assertEqual(res[0]["has_hyperlink"], "No")
        self.assertTrue(res[0]["is_unlinked"])

    def test_funding_news_mention_is_not_pitched(self):
        html = """<html><head><title>Startup news and updates: daily roundup</title></head><body><main>
            <p>Venture capital fund Finvolve and India Accelerator have invested an undisclosed amount
            in Bengaluru-based Soket AI Labs as part of its seed funding round.</p></main></body></html>"""
        res = self.monitor.inspect_content("https://news.example.com/roundup", html)
        self.assertEqual(res[0]["brand"], "India Accelerator")
        self.assertTrue(res[0]["is_unlinked"])
        self.assertFalse(res[0]["pitchable"])
        self.assertIn("not about coworking", res[0]["verification_status"])

    def test_coworking_mention_of_parent_is_pitched(self):
        html = """<html><head><title>India Accelerator opens new co-working centre in Surat</title></head>
            <body><p>India Accelerator has opened a 10,000 sq ft centre in Surat.</p></body></html>"""
        res = self.monitor.inspect_content("https://news.example.com/surat", html)
        self.assertTrue(res[0]["pitchable"])
        self.assertEqual(res[0]["verification_status"], "Verified (Live Page)")

    def test_whole_word_matching_avoids_false_positives(self):
        html = "<html><body><p>The best India spaces for remote work, and Asia Spaces too.</p></body></html>"
        self.assertEqual(self.monitor.inspect_content("https://x.example.com/a", html), [])

    def test_records_fill_every_sheet_column(self):
        html = "<html><head><title>Story</title></head><body><p>IA Spaces opened.</p></body></html>"
        rec = self.monitor.inspect_content("https://x.example.com/a", html)[0]
        self.assertEqual(rec["mentioned_url"], "https://x.example.com/a")
        self.assertEqual(rec["page_title"], "Story")
        for header in SHEET_HEADERS["Brand_Mentions"]:
            if header in ("Last Seen", "Team Notes"):
                continue
            key = header.lower().replace(" ", "_")
            self.assertIn(key, rec, f"missing value for column {header}")

    def test_context_comes_from_article_text_not_navigation(self):
        html = ("<html><body><nav><a href='/'>Home</a> IA Spaces partners menu</nav>"
                "<article><p>Last week IA Spaces opened a new coworking centre in Surat with 280 desks.</p></article>"
                "</body></html>")
        rec = self.monitor.inspect_content("https://news.example.com/s", html)[0]
        self.assertIn("opened a new coworking centre", rec["context"])
        self.assertNotIn("partners menu", rec["context"])

    def test_failed_fetch_produces_no_rows(self):
        self.assertEqual(self.monitor.analyze_url("https://blocked.example.com/"), [])


if __name__ == "__main__":
    unittest.main()
