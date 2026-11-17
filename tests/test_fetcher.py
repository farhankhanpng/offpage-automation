"""Tests for the shared polite fetcher and robots.txt handling."""

import io
import os
import sys
import unittest
import urllib.error

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.utils.fetcher import PoliteFetcher  # noqa: E402
from src.utils.health import FAILING, RunHealth  # noqa: E402
from src.utils.rate_limiter import PoliteRateLimiter  # noqa: E402

UA = "IASpacesSEOBot/1.1"


def limiter(robots_status, robots_body=""):
    return PoliteRateLimiter(default_delay=0, user_agent=UA,
                             robots_fetcher=lambda _url: (robots_status, robots_body))


class ScriptedOpener:
    """Returns queued responses; an int queues an HTTPError with that code."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, headers))
        r = self.responses.pop(0)
        if isinstance(r, int):
            raise urllib.error.HTTPError(url, r, "err", {}, io.BytesIO(b""))
        return 200, url, {}, r.encode()


class TestRobots(unittest.TestCase):

    def test_robots_403_means_allowed(self):
        # Python's RobotFileParser treats 401/403 as "disallow all"; Google treats 4xx as allow.
        self.assertTrue(limiter(403).is_allowed_by_robots("https://inc42.com/features/x"))

    def test_robots_5xx_means_temporarily_disallowed(self):
        self.assertFalse(limiter(503).is_allowed_by_robots("https://example.com/a"))

    def test_robots_rules_are_applied_for_our_user_agent(self):
        rl = limiter(200, "User-agent: *\nDisallow: /private/\n")
        self.assertTrue(rl.is_allowed_by_robots("https://example.com/public"))
        self.assertFalse(rl.is_allowed_by_robots("https://example.com/private/page"))


class TestFetcher(unittest.TestCase):

    def make(self, opener, robots=404, health=None):
        return PoliteFetcher(user_agent=UA, delay=0, max_retries=2, rate_limiter=limiter(robots),
                             opener=opener, health=health, max_backoff=0)

    def test_success_uses_our_user_agent_and_is_cached(self):
        opener = ScriptedOpener("<html>ok</html>")
        f = self.make(opener)
        self.assertTrue(f.fetch("https://a.example/x")["ok"])
        self.assertTrue(f.fetch("https://a.example/x")["ok"])
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(opener.calls[0][1]["User-Agent"], UA)

    def test_429_is_retried(self):
        f = self.make(ScriptedOpener(429, "<html>ok</html>"))
        res = f.fetch("https://a.example/y")
        self.assertTrue(res["ok"])

    def test_404_is_not_retried_and_recorded(self):
        health = RunHealth()
        opener = ScriptedOpener(404)
        res = self.make(opener, health=health).fetch("https://a.example/missing", source="backlink check")
        self.assertFalse(res["ok"])
        self.assertEqual(res["http_code"], 404)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(health.status(), FAILING)
        self.assertEqual(health.exit_code(), 2)

    def test_robots_block_skips_fetch(self):
        opener = ScriptedOpener()
        res = self.make(opener, robots=503).fetch("https://a.example/z")
        self.assertTrue(res["robots_blocked"])
        self.assertEqual(opener.calls, [])


if __name__ == "__main__":
    unittest.main()
