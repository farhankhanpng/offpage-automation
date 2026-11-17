"""Shared polite page fetcher.

One PoliteFetcher is created per pipeline run and passed to every module, so:
  - the per-domain delay applies across mention, backlink and competitor checks;
  - each URL is downloaded at most once per run (results are cached);
  - 429 / 503 responses are retried with backoff (honouring Retry-After, capped);
  - every attempt is recorded in RunHealth, so failures are visible in reports.
"""

import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional

from .logger import get_logger
from .rate_limiter import PoliteRateLimiter

logger = get_logger("Fetcher")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_BODY_BYTES = 5_000_000


def _default_opener(url: str, headers: Dict[str, str], timeout: float):
    """Return (status, final_url, response_headers, body_bytes). Raises HTTPError / URLError."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.getcode() or 200, resp.geturl(), dict(resp.headers), resp.read(MAX_BODY_BYTES)


class PoliteFetcher:
    """Fetches pages politely with robots.txt checks, retries and per-run caching."""

    def __init__(
        self,
        user_agent: str,
        timeout: float = 15.0,
        delay: float = 2.0,
        max_retries: int = 2,
        respect_robots: bool = True,
        rate_limiter: Optional[PoliteRateLimiter] = None,
        opener: Optional[Callable] = None,
        health=None,
        max_backoff: float = 30.0,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.respect_robots = respect_robots
        self.rate_limiter = rate_limiter or PoliteRateLimiter(
            default_delay=delay, user_agent=user_agent, timeout=min(timeout, 10.0)
        )
        self._opener = opener or _default_opener
        self.health = health
        self.max_backoff = max_backoff
        self._cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def from_settings(cls, settings: Dict[str, Any], health=None, **overrides) -> "PoliteFetcher":
        crawler = settings.get("crawler", {})
        kwargs = dict(
            user_agent=crawler.get("user_agent", "IASpaces-OffPage-Bot/1.0 (+https://iaspaces.co)"),
            timeout=float(crawler.get("timeout_seconds", 15)),
            delay=float(crawler.get("request_delay_seconds", 2.0)),
            max_retries=int(crawler.get("max_retries", 2)),
            respect_robots=bool(crawler.get("respect_robots_txt", True)),
            health=health,
        )
        kwargs.update(overrides)
        return cls(**kwargs)

    def _record(self, source: str, ok: bool, url: str, detail: str = ""):
        if self.health is not None:
            self.health.record(source, ok, url=url, detail=detail)

    def fetch(self, url: str, source: str = "page") -> Dict[str, Any]:
        """Fetch url. Returns a dict:
        {ok, status, http_code, html, final_url, error, robots_blocked}
        status is one of: "Success", "Blocked by robots.txt", "HTTP <code>", "Fetch Error".
        """
        if url in self._cache:
            return self._cache[url]

        result: Dict[str, Any] = {
            "ok": False, "status": "", "http_code": 0, "html": "",
            "final_url": url, "error": "", "robots_blocked": False,
        }

        if self.respect_robots and not self.rate_limiter.is_allowed_by_robots(url):
            result.update(status="Blocked by robots.txt", robots_blocked=True,
                          error="robots.txt disallows this URL for our user agent")
            logger.info(f"Skipped (robots.txt): {url}")
            self._record(source, False, url, "robots.txt disallow")
            self._cache[url] = result
            return result

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }

        attempt = 0
        while True:
            self.rate_limiter.wait_if_needed(url)
            try:
                status, final_url, _hdrs, body = self._opener(url, headers, self.timeout)
                result.update(
                    ok=200 <= status < 300, status="Success" if 200 <= status < 300 else f"HTTP {status}",
                    http_code=status, final_url=final_url or url,
                    html=body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or ""),
                )
                break
            except urllib.error.HTTPError as e:
                code = e.code
                if code in RETRYABLE_STATUS and attempt < self.max_retries:
                    wait = self._retry_after(e, attempt)
                    logger.info(f"HTTP {code} from {url}; retrying in {wait:.0f}s")
                    time.sleep(wait)
                    attempt += 1
                    continue
                result.update(status=f"HTTP {code}", http_code=code, error=f"HTTP Error {code}")
                break
            except Exception as e:  # network errors, timeouts, TLS
                if attempt < self.max_retries:
                    time.sleep(min(self.max_backoff, 2 ** attempt))
                    attempt += 1
                    continue
                result.update(status="Fetch Error", error=str(e)[:160])
                break

        if not result["ok"]:
            logger.warning(f"Fetch failed ({result['status']}): {url} {result['error']}".rstrip())
        self._record(source, result["ok"], url, "" if result["ok"] else (result["error"] or result["status"]))
        self._cache[url] = result
        return result

    def _retry_after(self, err: urllib.error.HTTPError, attempt: int) -> float:
        header = ""
        try:
            header = (err.headers or {}).get("Retry-After", "") if err.headers else ""
        except Exception:
            header = ""
        if header and str(header).strip().isdigit():
            return min(self.max_backoff, float(header))
        return min(self.max_backoff, 5.0 * (2 ** attempt))
