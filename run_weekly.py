"""IA Spaces - Weekly Off-Page SEO & Citation pipeline.

1. Directory listings: fetch each listing and compare it with the master NAP
2. Competitor coverage on the pages in data/competitors_seed.csv (fetched pages only -
   a page that fails to load is reported in Run Health, never written as a row)
3. Backlink checks
4. Google Sheets sync (Citations, Competitors, Backlinks, Dashboard) + local cache
5. Weekly Markdown report with a Run Health section

Usage:
  python run_weekly.py            # live run
  python run_weekly.py --dry-run  # fixtures only: no network, no Sheet writes

Exit codes: 0 ok / degraded, 1 a required integration failed, 2 nothing worked.
"""

import argparse
import os
import sys
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.backlinks.backlink_monitor import BacklinkMonitor  # noqa: E402
from src.citations.citation_tracker import CitationTracker  # noqa: E402
from src.competitors.competitor_tracker import CompetitorTracker, competitors_from_config  # noqa: E402
from src.pipeline import build_context  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

logger = get_logger("WeeklyRunner")


def run_weekly_pipeline(dry_run: bool = False, base_dir: str = BASE_DIR, fetcher=None, spreadsheet=None) -> Dict[str, Any]:
    ctx = build_context(base_dir, dry_run=dry_run, fetcher=fetcher, spreadsheet=spreadsheet)
    logger.info("=" * 65)
    logger.info(f"IA SPACES WEEKLY OFF-PAGE & CITATION PIPELINE - {'DRY RUN (fixtures)' if dry_run else 'LIVE RUN'}")
    logger.info("=" * 65)

    nap_path = ctx.path(ctx.settings.get("paths", {}).get("master_nap_csv", "data/ia-spaces-nap-master.csv"))
    if not os.path.exists(nap_path):
        ctx.health.add_issue(f"Master NAP file not found at {nap_path}; citation checks cannot run")
    citation_tracker = CitationTracker(master_nap_csv=nap_path, fetcher=ctx.fetcher)
    competitor_tracker = CompetitorTracker(competitors_from_config(ctx.competitors_cfg))
    backlink_monitor = BacklinkMonitor(fetcher=ctx.fetcher,
                                       legacy_targets=ctx.settings.get("backlinks", {}).get("legacy_targets"))

    citations = [
        citation_tracker.audit_listing(
            directory_name=row.get("directory_name", ""),
            listing_url=row.get("listing_url", ""),
            hub_name=row.get("hub_name", ""),
        )
        for row in ctx.read_csv("data/citations_seed.csv")
        if row.get("directory_name")
    ]

    competitor_rows = []
    for row in ctx.read_csv("data/competitors_seed.csv"):
        url = row.get("source_url", "")
        if not url:
            continue
        res = ctx.fetcher.fetch(url, source="competitor page")
        if res.get("ok"):
            competitor_rows.extend(
                competitor_tracker.analyze_page_for_competitors(url, res["html"], page_title=row.get("title", ""))
            )
    competitor_rows = list({c["id"]: c for c in competitor_rows}.values())

    backlinks = backlink_monitor.audit_backlink_list(ctx.read_csv("data/backlinks_seed.csv"))

    s = ctx.sheets
    s.sync_tab("Citations", citations)
    s.sync_tab("Competitors", competitor_rows)
    s.sync_tab("Backlinks", backlinks)

    def count(status):
        return sum(1 for c in citations if c.get("nap_status") == status)

    s.sync_tab("Dashboard", ctx.dashboard({
        "Weekly: Listings Matching Master NAP": count("Matches Master NAP"),
        "Weekly: Listings Needing Correction": count("Correction Needed"),
        "Weekly: Listings To Check By Hand": count("Could Not Verify"),
        "Weekly: Placeholder Listing URLs": count("Placeholder URL"),
        "Weekly: Competitor Coverage Rows": len(competitor_rows),
    }), key_field="Metric")

    report = ctx.reports.generate_weekly_report(
        citations=citations, competitor_opps=competitor_rows, backlinks=backlinks,
        health=ctx.health, sheets_status=ctx.sheets_status(), label=ctx.label,
    )
    s.log_activity("WEEKLY_RUN", ctx.health.status().upper(), ctx.health.summary_line())
    s.flush()

    logger.info(f"WEEKLY PIPELINE FINISHED - status {ctx.health.status()} ({ctx.health.summary_line()}). Report: {report}")
    return {"report": report, "health": ctx.health, "citations": citations,
            "competitors": competitor_rows, "backlinks": backlinks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IA Spaces Weekly Off-Page SEO Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Use fixture pages; no network, no Sheet writes")
    args = parser.parse_args()
    result = run_weekly_pipeline(dry_run=args.dry_run)
    sys.exit(result["health"].exit_code())
