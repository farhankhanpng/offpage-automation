"""Unit tests for HTML parsing, metadata extraction, links and snippet context.
"""

import unittest
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.utils.html_parser import parse_html_content, find_mention_context


class TestHTMLParser(unittest.TestCase):

    def test_parse_html_title_and_meta(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Best Coworking Spaces in Delhi NCR</title>
            <meta name="description" content="A comprehensive guide to top flexible office hubs.">
            <link rel="canonical" href="https://example.com/coworking-guide">
        </head>
        <body>
            <h1>Office Spaces</h1>
            <p>Here are the top options in Delhi NCR.</p>
        </body>
        </html>
        """
        res = parse_html_content(html, base_url="https://example.com")
        self.assertEqual(res["title"], "Best Coworking Spaces in Delhi NCR")
        self.assertEqual(res["meta_description"], "A comprehensive guide to top flexible office hubs.")
        self.assertEqual(res["canonical"], "https://example.com/coworking-guide")
        self.assertIn("Here are the top options in Delhi NCR.", res["body_text"])

    def test_parse_html_links_extraction(self):
        html = """
        <div>
            <a href="/about-us" rel="nofollow">About Us</a>
            <a href="https://iaspaces.co/gurgaon" rel="noopener">IA Spaces Gurgaon Hub</a>
        </div>
        """
        res = parse_html_content(html, base_url="https://example.com")
        links = res["links"]
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["href"], "https://example.com/about-us")
        self.assertEqual(links[0]["anchor_text"], "About Us")
        self.assertEqual(links[0]["rel"], "nofollow")

        self.assertEqual(links[1]["href"], "https://iaspaces.co/gurgaon")
        self.assertEqual(links[1]["anchor_text"], "IA Spaces Gurgaon Hub")

    def test_find_mention_context(self):
        text = "Startups across India are decentralizing. IA Spaces has added flexible workspaces in Tier-2 cities like Indore. Enterprise demand remains strong."
        context = find_mention_context(text, "IA Spaces", window=30)
        self.assertIn("IA Spaces", context)
        self.assertTrue(context.startswith("..."))
        self.assertTrue(context.endswith("..."))


if __name__ == "__main__":
    unittest.main()
