"""Run health tracking.

Every network-dependent step records success/failure here. The runners use it to:
  - write an honest "System Status" to the Dashboard (Healthy / Degraded / Failing);
  - add a "Run Health" section to the reports listing what failed;
  - exit non-zero when nothing worked, so GitHub Actions marks the run failed and
    emails the repo owner (GitHub's default notification for failed scheduled runs).
"""

from collections import OrderedDict
from typing import Dict, List

HEALTHY = "Healthy"
DEGRADED = "Degraded"
FAILING = "Failing"


class RunHealth:
    def __init__(self):
        self.sources: "OrderedDict[str, Dict[str, int]]" = OrderedDict()
        self.failures: List[Dict[str, str]] = []
        self.issues: List[str] = []

    def record(self, source: str, ok: bool, url: str = "", detail: str = ""):
        stats = self.sources.setdefault(source, {"attempted": 0, "succeeded": 0})
        stats["attempted"] += 1
        if ok:
            stats["succeeded"] += 1
        else:
            self.failures.append({"source": source, "url": url, "detail": detail})

    def add_issue(self, message: str):
        """A run-level problem that is not tied to one URL (e.g. Sheets not connected)."""
        if message not in self.issues:
            self.issues.append(message)

    @property
    def attempted(self) -> int:
        return sum(s["attempted"] for s in self.sources.values())

    @property
    def succeeded(self) -> int:
        return sum(s["succeeded"] for s in self.sources.values())

    def status(self) -> str:
        if self.attempted and self.succeeded == 0:
            return FAILING
        if self.issues or self.failures:
            return DEGRADED
        return HEALTHY

    def summary_line(self) -> str:
        parts = [f"{name}: {s['succeeded']}/{s['attempted']} ok" for name, s in self.sources.items()]
        return "; ".join(parts) if parts else "no network checks ran"

    def exit_code(self) -> int:
        """2 = nothing worked; 1 = a required integration failed; 0 otherwise."""
        if self.status() == FAILING:
            return 2
        if any(i.startswith("REQUIRED:") for i in self.issues):
            return 1
        return 0
