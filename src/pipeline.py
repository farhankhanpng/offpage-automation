"""Shared setup for the daily and weekly runners.

build_context() wires one RunHealth, one PoliteFetcher, one GoogleSheetsClient and one
ReportGenerator per run. In dry-run mode:
  - pages come from built-in fixtures (no network);
  - nothing is written to Google Sheets or to the real cache: data goes to
    data/dry_run_cache/ and reports to reports/dry-run/ (both git-ignored).
"""

import csv
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .reporting.report_generator import ReportGenerator
from .sheets.sheets_client import GoogleSheetsClient
from .utils.config_loader import load_settings, load_yaml, resolve_path
from .utils.fetcher import PoliteFetcher
from .utils.health import RunHealth
from .utils.time_utils import now_ist_str

FIXTURE_HTML = """<html><head><title>{title}</title></head><body>
<article><h1>{title}</h1>
<p>Flexible workspace demand keeps growing across India, from Gurugram and Noida to Tier-2 cities such as
Indore and Surat. Coworking operators like Awfis and Innov8 continue to expand their managed office portfolios.</p>
<p>IA Spaces, the coworking network of India Accelerator, recently opened a new centre.</p>
<a href="https://www.awfis.com/">Awfis</a>
<p>Contact the editor: <a href="mailto:editor@{domain}">editor@{domain}</a></p>
</article></body></html>"""


class FixtureFetcher:
    """Dry-run stand-in for PoliteFetcher: every URL returns a fixture page."""

    def __init__(self, health: RunHealth):
        self.health = health

    def fetch(self, url: str, source: str = "page") -> Dict[str, Any]:
        from .utils.url_utils import extract_domain
        domain = extract_domain(url) or "example.com"
        slug = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").replace(".html", "") or domain
        html = FIXTURE_HTML.format(title=f"[Fixture] {slug.title()}"[:90], domain=domain)
        self.health.record(source, True, url=url)
        return {"ok": True, "status": "Success", "http_code": 200, "html": html,
                "final_url": url, "error": "", "robots_blocked": False}


@dataclass
class RunContext:
    base_dir: str
    dry_run: bool
    settings: Dict[str, Any]
    keywords: Dict[str, Any]
    competitors_cfg: Dict[str, Any]
    health: RunHealth
    fetcher: Any
    sheets: GoogleSheetsClient
    reports: ReportGenerator
    label: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def path(self, relative: str) -> str:
        return resolve_path(self.base_dir, relative)

    def read_csv(self, relative: str) -> List[Dict[str, str]]:
        p = self.path(relative)
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8-sig", newline="") as f:
            return [{k: (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]

    def sheets_status(self) -> str:
        if self.dry_run:
            return "Dry run - nothing written to Google Sheets"
        if self.sheets.is_connected:
            return "Connected"
        return f"Not connected ({self.sheets.connection_error or 'offline'}) - local cache only"

    def dashboard(self, metrics: Dict[str, Any]) -> List[Dict[str, str]]:
        now = now_ist_str()
        rows = [{"Metric": k, "Value": str(v), "Last Updated": now} for k, v in metrics.items()]
        rows.append({"Metric": "System Status", "Value": f"{self.health.status()} - {self.health.summary_line()}",
                     "Last Updated": now})
        return rows


def build_context(base_dir: str, dry_run: bool = False, fetcher=None, spreadsheet=None) -> RunContext:
    settings = load_settings(base_dir)
    keywords = load_yaml(os.path.join(base_dir, "config", "keywords.yaml"))
    competitors_cfg = load_yaml(os.path.join(base_dir, "config", "competitors.yaml"))
    health = RunHealth()
    sheets_cfg = settings.get("sheets", {})

    if fetcher is None:
        fetcher = FixtureFetcher(health) if dry_run else PoliteFetcher.from_settings(settings, health=health)
    elif getattr(fetcher, "health", "missing") is None:
        fetcher.health = health

    if dry_run:
        offline_dir = resolve_path(base_dir, "data/dry_run_cache")
        reports_dir = resolve_path(base_dir, "reports/dry-run")
    else:
        offline_dir = resolve_path(base_dir, "data/sheets_offline_cache")
        reports_dir = resolve_path(base_dir, settings.get("paths", {}).get("reports_dir", "reports"))

    sheets = GoogleSheetsClient(
        credentials_path=resolve_path(base_dir, sheets_cfg.get("service_account_path", "secrets/google-service-account.json")),
        sheet_name=sheets_cfg.get("sheet_name", "IA Spaces - Off-Page SEO Master"),
        sheet_url=sheets_cfg.get("sheet_url") or None,
        sheet_id=sheets_cfg.get("sheet_id") or None,
        offline_dir=offline_dir,
        offline_only=dry_run,
        tombstones_path=resolve_path(base_dir, sheets_cfg.get("tombstones_file", "data/purged_ids.txt")),
        retention_days=int(sheets_cfg.get("retention_days", 90)),
        spreadsheet=spreadsheet,
    )

    if not dry_run and sheets_cfg.get("require_connection") and not sheets.is_connected:
        health.add_issue(f"REQUIRED: Google Sheets not connected ({sheets.connection_error or 'unknown error'})")
    elif not dry_run and not sheets.is_connected:
        health.add_issue(f"Google Sheets not connected ({sheets.connection_error or 'offline'}); wrote local cache only")

    return RunContext(
        base_dir=base_dir, dry_run=dry_run, settings=settings, keywords=keywords,
        competitors_cfg=competitors_cfg, health=health, fetcher=fetcher, sheets=sheets,
        reports=ReportGenerator(reports_dir=reports_dir),
        label=" - DRY RUN (fixtures)" if dry_run else "",
    )
