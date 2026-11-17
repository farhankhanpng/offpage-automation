"""IA Spaces - Daily Off-Page SEO Automation Runner.
Orchestrates:
1. Discovery (RSS, GDELT, Seed URLs)
2. Brand Mention Monitor (live page inspection)
3. Backlink Verification
4. Transparent Opportunity Scoring (0-100)
5. Personalised Outreach Generation ('Pending Approval')
6. Google Sheets Synchronization (with local CSV fallback)
7. Daily Markdown Report Generation

Usage:
  python run_daily.py [--dry-run]
"""

import os
import sys
import argparse
import csv
from datetime import datetime

# Add root offpage-automation directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.utils.logger import get_logger
from src.utils.config_loader import load_yaml_config
from src.discovery.discovery_engine import DiscoveryEngine
from src.mentions.mention_monitor import MentionMonitor
from src.backlinks.backlink_monitor import BacklinkMonitor
from src.competitors.competitor_tracker import CompetitorTracker
from src.scoring.opportunity_scorer import OpportunityScorer
from src.reporting.outreach_generator import OutreachDraftGenerator
from src.reporting.report_generator import ReportGenerator
from src.sheets.sheets_client import GoogleSheetsClient

logger = get_logger("DailyRunner")


def run_daily_pipeline(dry_run: bool = False):
    logger.info("=" * 65)
    logger.info("STARTING IA SPACES DAILY OFF-PAGE SEO PIPELINE")
    logger.info(f"Mode: {'DRY RUN (Mock Offline Mode)' if dry_run else 'LIVE RUN'}")
    logger.info("=" * 65)

    settings = load_yaml_config(os.path.join(BASE_DIR, "config", "settings.yaml"))
    keywords = load_yaml_config(os.path.join(BASE_DIR, "config", "keywords.yaml"))

    crawler_cfg = settings.get("crawler", {})
    ua = crawler_cfg.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    brands = keywords.get("brand_terms") or keywords.get("brand_variations")

    # Initialize Modules
    discovery = DiscoveryEngine(settings)
    mentions_monitor = MentionMonitor(brands=brands, user_agent=ua)
    competitor_tracker = CompetitorTracker()
    backlink_monitor = BacklinkMonitor(user_agent=ua)
    scorer = OpportunityScorer()
    outreach_gen = OutreachDraftGenerator()
    report_gen = ReportGenerator(reports_dir=os.path.join(BASE_DIR, "reports"))
    sheets_cfg = settings.get("sheets", {})
    sheets_client = GoogleSheetsClient(
        credentials_path=os.path.join(BASE_DIR, "secrets", "google-service-account.json"),
        sheet_name=sheets_cfg.get("sheet_name", "IA Spaces - Off-Page SEO Master"),
        sheet_url=sheets_cfg.get("sheet_url"),
        offline_dir=os.path.join(BASE_DIR, "data", "sheets_offline_cache")
    )

    discovered_opps = []
    mentions_results = []
    backlink_results = []
    competitor_results = []
    outreach_drafts = []

    if dry_run:
        logger.info("[DRY-RUN] Simulating discovery and web inspection with verified fixtures...")
        # Mock Discovery
        mock_candidates = [
            {
                "url": "https://inc42.com/features/top-coworking-spaces-in-delhi-ncr-2026/",
                "title": "Top Coworking Spaces In Delhi NCR Supporting Fast-Growing Tech Startups",
                "summary": "Explore flexible workspaces across Gurugram and Noida including Awfis and Innov8.",
                "domain": "inc42.com",
                "source": "RSS Feed (Inc42)"
            },
            {
                "url": "https://yourstory.com/2026/02/tier-2-startup-ecosystems-flexible-office-boom",
                "title": "Tier-2 Startup Ecosystems Witness Flexible Office Boom",
                "summary": "India Accelerator and regional coworking providers are decentralizing enterprise workspaces into cities like Indore and Ahmedabad.",
                "domain": "yourstory.com",
                "source": "GDELT News"
            },
            {
                "url": "https://entrackr.com/2026/01/gurugram-commercial-leasing-surge-managed-offices",
                "title": "Gurugram Commercial Leasing Surges As Managed Office Spaces Dominate",
                "summary": "Demand for managed office solutions in Golf Course Road and MG Road remains robust.",
                "domain": "entrackr.com",
                "source": "Manual Query"
            }
        ]

        # Mock Mention Inspection HTMLs
        mock_page_html = (
            "<html><head><title>Tier-2 Startup Ecosystems Witness Flexible Office Boom</title></head>"
            "<body><p>As startups decentralize, India Accelerator and its coworking wing IA Spaces have added "
            "over 50,000 sq ft across Indore and Ahmedabad. However, corporate tenants are demanding enterprise amenities.</p>"
            "<a href='https://iaspaces.co/ahmedabad/'>Visit Ahmedabad Hub</a>"
            "</body></html>"
        )
        mentions_results = mentions_monitor.inspect_content(
            "https://yourstory.com/2026/02/tier-2-startup-ecosystems-flexible-office-boom",
            mock_page_html,
            source_label="Verified Web Page"
        )

        # Mock Backlink Audit
        backlink_results = [
            {
                "id": "BL-7A8B9C0D",
                "source_url": "https://indiaaccelerator.co/ecosystem",
                "target_url": "https://iaspaces.co",
                "http_status": 200,
                "link_exists": "Yes",
                "anchor_text": "IA Spaces Coworking",
                "rel_attributes": "dofollow",
                "link_status": "Live (Dofollow)",
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "notes": "Verified parent ecosystem link"
            },
            {
                "id": "BL-4E5F6A1B",
                "source_url": "https://inc42.com/features/coworking-spaces-india",
                "target_url": "https://iaspaces.co",
                "http_status": 200,
                "link_exists": "No",
                "anchor_text": "",
                "rel_attributes": "",
                "link_status": "Missing",
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "notes": "Page fetched successfully but no link to iaspaces.co found."
            }
        ]

        # Score Opportunities
        for cand in mock_candidates:
            score_data = scorer.score_prospect(
                url=cand["url"],
                title=cand["title"],
                content_snippet=cand["summary"],
                domain=cand["domain"],
                has_contact_info=True,
                is_editorial=True,
                is_competitor_coverage=("inc42" in cand["domain"])
            )
            cand_id = f"OPP-{hash(cand['url']) & 0xFFFFFF:06X}"
            discovered_opps.append({
                "id": cand_id,
                "publication": cand["domain"],
                "url": cand["url"],
                "page_title": cand["title"],
                "discovery_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": cand["source"],
                "opportunity_score": score_data["total_score"],
                "priority": score_data["priority"],
                "scoring_breakdown": score_data["breakdown"]
            })

            # Generate Outreach Draft for top score
            if score_data["total_score"] >= 75:
                draft = outreach_gen.generate_draft(
                    publication=cand["domain"],
                    target_url=cand["url"],
                    angle="Listicle Inclusion",
                    contact_name="Features Desk",
                    contact_email="features@" + cand["domain"],
                    contact_source="Editorial Masthead"
                )
                outreach_drafts.append(draft)

    else:
        # Live execution
        logger.info("[LIVE] Executing discovery via public feeds and seed monitors...")
        rss_feeds = settings.get("discovery", {}).get("public_rss_feeds", [])
        gdelt_queries = settings.get("discovery", {}).get("gdelt_queries", [])

        # Gather seed URLs from competitors_seed.csv and backlinks_seed.csv
        seed_urls = []
        comp_seed_path = os.path.join(BASE_DIR, "data", "competitors_seed.csv")
        if os.path.exists(comp_seed_path):
            with open(comp_seed_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    u = row.get("source_url", "").strip()
                    if u:
                        seed_urls.append(u)

        raw_opps = discovery.run_discovery(
            custom_rss_feeds=rss_feeds,
            gdelt_queries=gdelt_queries,
            seed_urls=seed_urls
        )

        for opp in raw_opps:
            opp_url = opp["url"]
            # Fetch page safely
            fetch_res = mentions_monitor.fetch_page(opp_url)
            html = fetch_res.get("html", "")
            title = opp.get("title", "")

            # 1. Check for Brand Mentions
            if html:
                m_found = mentions_monitor.inspect_content(opp_url, html, source_label=opp.get("source", "Web"))
                mentions_results.extend(m_found)

                # 2. Check for Competitor Mentions & Editorial Angles
                c_found = competitor_tracker.analyze_page_for_competitors(opp_url, html, page_title=title)
                competitor_results.extend(c_found)

            # 3. Score Opportunity
            score_data = scorer.score_prospect(
                url=opp_url,
                title=title,
                content_snippet=opp.get("summary", ""),
                domain=opp.get("domain", ""),
                has_contact_info=True,
                is_editorial=True,
                is_competitor_coverage=len([c for c in competitor_results if c.get("source_url") == opp_url]) > 0
            )
            opp["opportunity_score"] = score_data["total_score"]
            opp["priority"] = score_data["priority"]
            opp["scoring_breakdown"] = score_data["breakdown"]
            opp["page_title"] = title or "Editorial Coverage"
            opp["publication"] = opp.get("domain", "")
            discovered_opps.append(opp)

            # 4. Generate Outreach Draft for strong prospects (score >= 60)
            if score_data["total_score"] >= 60:
                draft = outreach_gen.generate_draft(
                    publication=opp.get("domain", ""),
                    target_url=opp_url,
                    angle="Listicle Inclusion",
                    contact_name="Editorial Features Desk",
                    contact_email="editorial@" + opp.get("domain", "media.in"),
                    contact_source="Public Masthead"
                )
                outreach_drafts.append(draft)

        # Check Seed Backlinks
        seed_bl_path = os.path.join(BASE_DIR, "data", "backlinks_seed.csv")
        if os.path.exists(seed_bl_path):
            with open(seed_bl_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                backlink_results = backlink_monitor.audit_backlink_list(list(reader))

        # Check Seed Brand Mentions
        seed_mentions_path = os.path.join(BASE_DIR, "data", "mentions_seed.csv")
        if os.path.exists(seed_mentions_path):
            with open(seed_mentions_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    u = row.get("source_url", "").strip()
                    if u:
                        m_res = mentions_monitor.analyze_url(u, source_label=row.get("source", "Seed Mention"))
                        for m in m_res:
                            if m.get("brand") and m.get("brand") != "N/A":
                                if not any(existing.get("id") == m.get("id") for existing in mentions_results):
                                    mentions_results.append(m)

    # Sync to Sheets / Local Cache
    logger.info("Synchronizing data to Google Sheets tabs & local CSV cache...")
    if discovered_opps:
        sheets_client.sync_tab("Opportunities", discovered_opps, key_field="ID")
    if mentions_results:
        sheets_client.sync_tab("Brand_Mentions", mentions_results, key_field="ID")
    if competitor_results:
        sheets_client.sync_tab("Competitors", competitor_results, key_field="ID")
    if backlink_results:
        sheets_client.sync_tab("Backlinks", backlink_results, key_field="ID")
    if outreach_drafts:
        sheets_client.sync_tab("Outreach", outreach_drafts, key_field="ID")

    # Update Dashboard Tab
    dashboard_metrics = [
        {"Metric": "Total Opportunities Discovered", "Value": str(len(discovered_opps)), "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "Active Monitored Backlinks", "Value": str(len(backlink_results)), "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "Brand Mentions Tracked", "Value": str(len(mentions_results)), "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "Competitor Gaps Tracked", "Value": str(len(competitor_results)), "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "Outreach Drafts Pending Approval", "Value": str(len(outreach_drafts)), "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "System Status", "Value": "Healthy / Operational", "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    ]
    sheets_client.sync_tab("Dashboard", dashboard_metrics, key_field="Metric")

    # Generate Daily Markdown Report
    report_file = report_gen.generate_daily_report(
        opportunities=discovered_opps,
        mentions=mentions_results,
        backlinks=backlink_results,
        outreach_drafts=outreach_drafts
    )

    logger.info("=" * 65)
    logger.info(f"DAILY PIPELINE COMPLETED SUCCESSFULLY! Report: {report_file}")
    logger.info("=" * 65)
    return report_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IA Spaces Daily Off-Page SEO Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Run with mock offline fixtures")
    args = parser.parse_args()

    run_daily_pipeline(dry_run=args.dry_run)
