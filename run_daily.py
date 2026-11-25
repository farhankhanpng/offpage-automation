"""IA Spaces - Daily Off-Page SEO pipeline.

1. Discovery: public RSS feeds + GDELT (relevance-filtered) + seed URLs
2. Fetch each candidate page once (shared polite fetcher, robots.txt respected)
3. Brand mentions and competitor coverage on the fetched page
4. Transparent scoring (pages that were not fetched can't qualify for outreach)
5. Outreach drafts ("Pending Approval" - never sent)
6. Backlink checks and brand-mention seed checks
7. Google Sheets sync (team edits preserved) + local CSV cache
8. Markdown report with a Run Health section

Usage:
  python run_daily.py            # live run
  python run_daily.py --dry-run  # fixtures only: no network, no Sheet writes

Exit codes: 0 ok / degraded, 1 a required integration failed (e.g. Sheets in CI), 2 nothing worked.
"""

import argparse
import os
import sys
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.backlinks.backlink_monitor import BacklinkMonitor  # noqa: E402
from src.competitors.competitor_tracker import CompetitorTracker, competitors_from_config  # noqa: E402
from src.discovery.discovery_engine import DiscoveryEngine  # noqa: E402
from src.mentions.mention_monitor import MentionMonitor  # noqa: E402
from src.pipeline import build_context  # noqa: E402
from src.reporting.outreach_generator import OutreachDraftGenerator, pick_contact  # noqa: E402
from src.scoring.opportunity_scorer import OpportunityScorer  # noqa: E402
from src.utils.html_parser import parse_html_content  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from src.utils.text_match import find_contact_emails  # noqa: E402
from src.utils.url_utils import extract_domain  # noqa: E402

logger = get_logger("DailyRunner")

# The brand a link request is about: IA Spaces first, then the parent's name, and the old
# MySOHO name last (MySOHO was acquired and now operates as part of IA Spaces).
BRAND_PRIORITY = ["ia spaces", "iaspaces.co", "india accelerator coworking", "india accelerator spaces",
                  "india accelerator", "mysoho"]


# News digests (one per day) and data trackers are not pitch targets: each new edition would
# create another draft to a different journalist at the same publication.
DIGEST_TITLE_TERMS = ["daily roundup", "weekly roundup", "news roundup", "startup news and updates",
                      "news and updates", "live updates", "funding roundup", "weekly wrap", "tracker"]


def is_digest_page(title: str) -> bool:
    t = (title or "").lower()
    return any(term in t for term in DIGEST_TITLE_TERMS)


def pick_unlinked(mentions: List[Dict[str, Any]]):
    """The unlinked mention to pitch. Only workspace mentions qualify (an India Accelerator
    funding story should not be asked to link to iaspaces.co); IA Spaces is preferred."""
    unlinked = [m for m in mentions if m.get("is_unlinked") and m.get("pitchable", True)]
    if not unlinked:
        return None

    def rank(m):
        b = m.get("brand", "").lower()
        return BRAND_PRIORITY.index(b) if b in BRAND_PRIORITY else len(BRAND_PRIORITY)
    return sorted(unlinked, key=rank)[0]


def run_daily_pipeline(dry_run: bool = False, base_dir: str = BASE_DIR, fetcher=None, spreadsheet=None,
                       use_feeds: bool = True) -> Dict[str, Any]:
    ctx = build_context(base_dir, dry_run=dry_run, fetcher=fetcher, spreadsheet=spreadsheet)
    logger.info("=" * 65)
    logger.info(f"IA SPACES DAILY OFF-PAGE SEO PIPELINE - {'DRY RUN (fixtures)' if dry_run else 'LIVE RUN'}")
    logger.info("=" * 65)

    brands = ctx.keywords.get("brand_terms") or ["IA Spaces", "India Accelerator", "MySOHO"]
    competitors = competitors_from_config(ctx.competitors_cfg)
    outreach_cfg = ctx.settings.get("outreach", {})
    min_score = int(outreach_cfg.get("min_score", 65))
    legacy_targets = ctx.settings.get("backlinks", {}).get("legacy_targets")

    mentions_monitor = MentionMonitor(brands=brands, fetcher=ctx.fetcher)
    competitor_tracker = CompetitorTracker(competitors)
    backlink_monitor = BacklinkMonitor(fetcher=ctx.fetcher, legacy_targets=legacy_targets)
    scorer = OpportunityScorer()
    nap_rel = ctx.settings.get("paths", {}).get("master_nap_csv", "data/ia-spaces-nap-master.csv")
    outreach = OutreachDraftGenerator(ctx.settings.get("brand_facts"), hubs=ctx.read_csv(nap_rel),
                                      sender=outreach_cfg.get("sender"))
    discovery = DiscoveryEngine(ctx.settings, health=ctx.health,
                                relevance_terms=list(brands) + [c["name"] for c in competitors])

    disc_cfg = ctx.settings.get("discovery", {})
    candidates = discovery.run_discovery(
        custom_rss_feeds=disc_cfg.get("public_rss_feeds", []) if use_feeds and not dry_run else [],
        gdelt_queries=disc_cfg.get("gdelt_queries", []) if use_feeds and not dry_run else [],
        seed_urls=ctx.read_csv("data/competitors_seed.csv"),
    )

    opportunities: List[Dict[str, Any]] = []
    mentions: List[Dict[str, Any]] = []
    competitor_rows: List[Dict[str, Any]] = []
    drafts: Dict[str, Dict[str, Any]] = {}

    for cand in candidates:
        url = cand["url"]
        res = ctx.fetcher.fetch(url, source="candidate page")
        title = cand.get("title", "")
        page_mentions, page_comps, emails, body = [], [], [], cand.get("summary", "")
        if res.get("ok"):
            parsed = parse_html_content(res["html"], base_url=url)
            title = title or parsed.get("title", "")
            body = parsed.get("body_text", "")
            page_mentions = mentions_monitor.inspect_content(url, res["html"], source_label=cand.get("source", "Web"))
            page_comps = competitor_tracker.analyze_page_for_competitors(url, res["html"], page_title=title)
            emails = find_contact_emails(res["html"], url)
            mentions.extend(page_mentions)
            competitor_rows.extend(page_comps)

        score = scorer.score_prospect(
            url=url, title=title, content_snippet=body, domain=cand.get("domain", ""),
            has_contact_info=bool(emails), is_editorial=bool(res.get("ok")),
            is_competitor_coverage=bool(page_comps), page_fetched=bool(res.get("ok")),
        )
        opportunities.append({
            "id": cand["id"],
            "publication": cand.get("domain") or extract_domain(url),
            "url": url,
            "page_title": title or "(title not available)",
            "discovery_date": cand.get("discovery_date", ""),
            "source": cand.get("source", ""),
            "page_fetched": "Yes" if res.get("ok") else f"No - {res.get('status')}",
            "opportunity_score": score["total_score"],
            "priority": score["priority"],
            "scoring_breakdown": score["breakdown"],
        })

        if res.get("ok") and scorer.qualifies_for_outreach(score, min_score) and not is_digest_page(title):
            unlinked = pick_unlinked(page_mentions)
            if unlinked:
                angle = "Unlinked Brand Mention"
            elif page_comps:
                angle = outreach.angle_for(page_comps[0]["editorial_angle"])
            else:
                angle = outreach.angle_for(CompetitorTracker.editorial_angle(title, body))
            contact = pick_contact(emails)
            draft = outreach.generate_draft(
                publication=cand.get("domain", ""), target_url=url, angle=angle,
                contact_email=contact, contact_source="Published on the page" if contact else None,
                page_title=title, brand=unlinked["brand"] if unlinked else "IA Spaces",
            )
            drafts[draft["id"]] = draft

    # Known coverage pages: brand mentions without a link become reclamation drafts
    for row in ctx.read_csv("data/mentions_seed.csv"):
        url = row.get("source_url", "")
        if not url:
            continue
        found = mentions_monitor.analyze_url(url, source_label=row.get("source") or "Seed Mention")
        mentions.extend(found)
        unlinked = pick_unlinked(found)
        if unlinked:
            res = ctx.fetcher.fetch(url, source="mention check")
            contact = pick_contact(find_contact_emails(res.get("html", ""), url))
            draft = outreach.generate_draft(
                publication=extract_domain(url), target_url=unlinked["mentioned_url"],
                angle="Unlinked Brand Mention", contact_email=contact,
                contact_source="Published on the page" if contact else None,
                page_title=unlinked.get("page_title", ""), brand=unlinked["brand"],
            )
            drafts[draft["id"]] = draft

    backlinks = backlink_monitor.audit_backlink_list(ctx.read_csv("data/backlinks_seed.csv"))

    # De-duplicate mentions by stable ID
    mentions = list({m["id"]: m for m in mentions}.values())
    competitor_rows = list({c["id"]: c for c in competitor_rows}.values())
    draft_list = list(drafts.values())

    # Every tab is synced every run (even with no new rows) so purges and retention always apply.
    s = ctx.sheets
    s.sync_tab("Opportunities", opportunities)
    s.sync_tab("Brand_Mentions", mentions)
    s.sync_tab("Competitors", competitor_rows)
    s.sync_tab("Backlinks", backlinks)
    # Older drafts not found again today are rewritten on the current template too
    s.sync_tab("Outreach", draft_list, refresh_fn=outreach.refresh_existing)

    s.sync_tab("Dashboard", ctx.dashboard({
        "Total Opportunities Discovered": len(opportunities),
        "Candidate Pages Fetched": sum(1 for o in opportunities if o["page_fetched"] == "Yes"),
        "Active Monitored Backlinks": sum(1 for b in backlinks if str(b.get("link_status", "")).startswith("Live")),
        "Backlink Sources Checked": len(backlinks),
        "Brand Mentions Tracked": len(mentions),
        "Unlinked Brand Mentions": sum(1 for m in mentions if m.get("is_unlinked")),
        "Competitor Gaps Tracked": len(competitor_rows),
        "Outreach Drafts Pending Approval": len(draft_list),
    }), key_field="Metric")

    report = ctx.reports.generate_daily_report(
        opportunities=opportunities, mentions=mentions, backlinks=backlinks, outreach_drafts=draft_list,
        health=ctx.health, sheets_status=ctx.sheets_status(), label=ctx.label,
    )
    s.log_activity("DAILY_RUN", ctx.health.status().upper(), ctx.health.summary_line())
    s.flush()

    logger.info(f"DAILY PIPELINE FINISHED - status {ctx.health.status()} ({ctx.health.summary_line()}). Report: {report}")
    return {"report": report, "health": ctx.health, "opportunities": opportunities, "mentions": mentions,
            "backlinks": backlinks, "drafts": draft_list, "competitors": competitor_rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IA Spaces Daily Off-Page SEO Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Use fixture pages; no network, no Sheet writes")
    args = parser.parse_args()
    result = run_daily_pipeline(dry_run=args.dry_run)
    sys.exit(result["health"].exit_code())
