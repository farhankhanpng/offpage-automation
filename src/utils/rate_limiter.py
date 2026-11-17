"""Polite per-domain rate limiter and robots.txt checker.

robots.txt handling follows Google's documented behaviour rather than Python's
RobotFileParser defaults:
  - fetched with OUR user agent and a timeout (RobotFileParser.read() uses
    "Python-urllib" and no timeout, which bot-protection services often answer
    with 403 -- and Python then treats the whole site as disallowed);
  - 2xx  -> parse the rules;
  - 4xx  -> no usable robots.txt, crawling allowed;
  - 5xx  -> treat the site as temporarily disallowed;
  - network error -> unknown; allowed (the page fetch itself will then fail and be reported).
"""

import time
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

ALLOW_ALL = "allow_all"
DISALLOW_ALL = "disallow_all"


class PoliteRateLimiter:
    """Enforces polite delays between requests to the same domain and checks robots.txt.

    One instance should be shared by every module in a run so the delay is enforced
    across modules (mention, backlink and competitor checks often hit the same site).
    """

    def __init__(
        self,
        default_delay: float = 2.0,
        user_agent: str = "IASpaces-OffPage-Bot/1.0",
        robots_fetcher: Optional[Callable[[str], Tuple[int, str]]] = None,
        timeout: float = 10.0,
    ):
        self.default_delay = default_delay
        self.user_agent = user_agent
        self.timeout = timeout
        self.last_request_time: Dict[str, float] = {}
        self.robots_cache: Dict[str, object] = {}
        self._robots_fetcher = robots_fetcher or self._default_robots_fetch

    @staticmethod
    def get_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def wait_if_needed(self, url: str, delay: Optional[float] = None) -> None:
        """Sleep if required to keep a minimum delay between hits to the same domain."""
        domain = self.get_domain(url)
        if not domain:
            return
        min_delay = self.default_delay if delay is None else delay
        elapsed = time.time() - self.last_request_time.get(domain, 0.0)
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        self.last_request_time[domain] = time.time()

    def _default_robots_fetch(self, robots_url: str) -> Tuple[int, str]:
        """Return (status_code, body). status 0 means a network error."""
        import urllib.error
        import urllib.request

        req = urllib.request.Request(robots_url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.getcode() or 200, resp.read(512_000).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception:
            return 0, ""

    def _load_robots(self, url: str):
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        self.wait_if_needed(robots_url)
        status, body = self._robots_fetcher(robots_url)

        if 200 <= status < 300:
            rp = RobotFileParser()
            rp.parse(body.splitlines())
            return rp
        if 400 <= status < 500 or status == 0:
            return ALLOW_ALL
        return DISALLOW_ALL  # 5xx

    def is_allowed_by_robots(self, url: str) -> bool:
        """True when robots.txt permits fetching url for our user agent."""
        domain = self.get_domain(url)
        if not domain:
            return True
        if domain not in self.robots_cache:
            try:
                self.robots_cache[domain] = self._load_robots(url)
            except Exception:
                self.robots_cache[domain] = ALLOW_ALL

        rules = self.robots_cache[domain]
        if rules == ALLOW_ALL:
            return True
        if rules == DISALLOW_ALL:
            return False
        try:
            return rules.can_fetch(self.user_agent, url)
        except Exception:
            return True
