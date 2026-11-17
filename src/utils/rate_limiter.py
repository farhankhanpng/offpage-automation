"""Polite rate limiter and robots.txt compliance checker.
"""

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from typing import Dict, Optional


class PoliteRateLimiter:
    """Enforces polite delays between requests to the same domain and checks robots.txt."""

    def __init__(self, default_delay: float = 2.0, user_agent: str = "IASpaces-OffPage-Bot/1.0"):
        self.default_delay = default_delay
        self.user_agent = user_agent
        self.last_request_time: Dict[str, float] = {}
        self.robots_cache: Dict[str, Optional[RobotFileParser]] = {}

    def get_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def wait_if_needed(self, url: str, delay: Optional[float] = None) -> None:
        """Sleep if required to maintain minimum delay between hits to the same domain."""
        domain = self.get_domain(url)
        if not domain:
            return

        min_delay = delay if delay is not None else self.default_delay
        now = time.time()
        last_time = self.last_request_time.get(domain, 0.0)
        elapsed = now - last_time

        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)

        self.last_request_time[domain] = time.time()

    def is_allowed_by_robots(self, url: str) -> bool:
        """Check whether fetching the given URL is allowed by robots.txt.

        Caches RobotFileParser instances per domain. Fails open politely if unreachable.
        """
        domain = self.get_domain(url)
        if not domain:
            return True

        if domain not in self.robots_cache:
            try:
                parsed = urlparse(url)
                robots_url = f"{parsed.scheme}://{domain}/robots.txt"
                rp = RobotFileParser()
                rp.set_url(robots_url)
                # Polite read with short timeout handled by rp.read
                # If network fails or sandbox restricts, rp.read() raises or catches
                try:
                    rp.read()
                    self.robots_cache[domain] = rp
                except Exception:
                    self.robots_cache[domain] = None
            except Exception:
                self.robots_cache[domain] = None

        rp = self.robots_cache.get(domain)
        if rp is None:
            # If robots.txt cannot be fetched or parsed, default to allowing politely
            return True

        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True
