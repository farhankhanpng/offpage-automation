"""Unit tests for URL utilities, normalization, and stable ID generation.
"""

import unittest
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.utils.url_utils import normalize_url, extract_domain, generate_stable_id, is_valid_url


class TestURLUtils(unittest.TestCase):

    def test_normalize_url_strips_tracking(self):
        url = "https://example.com/blog/article/?utm_source=twitter&utm_medium=social&gclid=123"
        expected = "https://example.com/blog/article"
        self.assertEqual(normalize_url(url), expected)

    def test_normalize_url_trailing_slash(self):
        url = "https://iaspaces.co/gurgaon/mg-road/"
        expected = "https://iaspaces.co/gurgaon/mg-road"
        self.assertEqual(normalize_url(url), expected)

    def test_normalize_root_url(self):
        url = "https://iaspaces.co/"
        expected = "https://iaspaces.co/"
        self.assertEqual(normalize_url(url), expected)

    def test_extract_domain(self):
        self.assertEqual(extract_domain("https://www.iaspaces.co/about"), "iaspaces.co")
        self.assertEqual(extract_domain("http://sub.domain.com:8080/path"), "sub.domain.com")

    def test_generate_stable_id_deterministic(self):
        id1 = generate_stable_id("https://iaspaces.co/about", prefix="OPP")
        id2 = generate_stable_id("https://iaspaces.co/about?utm_source=test", prefix="OPP")
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("OPP-"))
        self.assertEqual(len(id1), 14)  # OPP- + 10 hex chars

    def test_is_valid_url(self):
        self.assertTrue(is_valid_url("https://iaspaces.co"))
        self.assertTrue(is_valid_url("http://example.com/test"))
        self.assertFalse(is_valid_url("not_a_url"))
        self.assertFalse(is_valid_url("ftp://invalid"))


if __name__ == "__main__":
    unittest.main()
