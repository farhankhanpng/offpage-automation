"""Unit tests for Brand Mention Monitor and unlinked mention detection.
"""

import unittest
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.mentions.mention_monitor import MentionMonitor


class TestMentionMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = MentionMonitor(
            brands=["IA Spaces", "India Accelerator", "MySOHO"],
            target_domains=["iaspaces.co", "www.iaspaces.co"]
        )

    def test_linked_mention_detection(self):
        html = """
        <html>
        <body>
            <p>We recently reviewed IA Spaces and their growth across NCR.</p>
            <a href="https://iaspaces.co/gurgaon/">Explore IA Spaces Hubs</a>
        </body>
        </html>
        """
        results = self.monitor.inspect_content("https://news.example.com/story", html)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["brand"], "IA Spaces")
        self.assertEqual(res["has_hyperlink"], "Yes")
        self.assertEqual(res["is_unlinked"], False)
        self.assertEqual(res["link_destination"], "https://iaspaces.co/gurgaon/")

    def test_unlinked_mention_detection(self):
        html = """
        <html>
        <body>
            <p>According to Ashish Bhatia, India Accelerator Coworking is seeing high occupancy.</p>
        </body>
        </html>
        """
        results = self.monitor.inspect_content("https://tech.example.com/coworking", html)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["brand"], "India Accelerator")
        self.assertEqual(res["has_hyperlink"], "No")
        self.assertEqual(res["is_unlinked"], True)
        self.assertEqual(res["link_destination"], "")


if __name__ == "__main__":
    unittest.main()
