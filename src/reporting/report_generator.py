"""Markdown Report Generator for daily and weekly off-page SEO tracking.
Generates structured Markdown reports saved in reports/.
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger("ReportGenerator")


class ReportGenerator:
    """Produces clean, executive-ready Markdown reports in reports/."""

    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_daily_report(
        self,
        opportunities: List[Dict[str, Any]],
        mentions: List[Dict[str, Any]],
        backlinks: List[Dict[str, Any]],
        outreach_drafts: List[Dict[str, Any]]
    ) -> str:
        """Generate structured Daily Off-Page SEO Discovery Report."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        unlinked_mentions = [m for m in mentions if m.get("is_unlinked") or m.get("has_hyperlink") == "No"]
        live_backlinks = [b for b in backlinks if "Live" in b.get("link_status", "")]
        missing_backlinks = [b for b in backlinks if b.get("link_status") == "Missing"]
        high_score_opps = [o for o in opportunities if o.get("priority") == "High" or (isinstance(o.get("opportunity_score"), (int, float)) and o.get("opportunity_score", 0) >= 70)]

        content = [
            f"# IA Spaces - Daily Off-Page SEO Report ({today_str})",
            f"*Generated at: {timestamp} IST*",
            "",
            "## Executive Summary",
            f"- **New Prospects Discovered:** {len(opportunities)}",
            f"- **High-Priority Opportunities:** {len(high_score_opps)}",
            f"- **Brand Mentions Checked:** {len(mentions)} ({len(unlinked_mentions)} unlinked)",
            f"- **Backlink Sources Audited:** {len(backlinks)} ({len(live_backlinks)} Live, {len(missing_backlinks)} Missing)",
            f"- **Outreach Drafts Queued:** {len(outreach_drafts)} (All strictly *Pending Approval*)",
            "",
            "---",
            "",
            "## 1. High-Priority Outreach Opportunities",
        ]

        if high_score_opps:
            content.append("| ID | Publication | URL | Score | Priority | Breakdown |")
            content.append("|---|---|---|---|---|---|")
            for opp in high_score_opps[:10]:
                content.append(
                    f"| `{opp.get('id')}` | {opp.get('publication') or opp.get('domain')} | "
                    f"[{opp.get('title') or 'Link'}]({opp.get('url')}) | "
                    f"**{opp.get('opportunity_score') or opp.get('total_score', 'N/A')}/100** | "
                    f"{opp.get('priority', 'High')} | {opp.get('scoring_breakdown') or opp.get('breakdown', '')} |"
                )
        else:
            content.append("*No high-priority prospects discovered in this run.*")

        content.extend([
            "",
            "## 2. Brand Mentions & Unlinked Attributions",
        ])

        if mentions:
            content.append("| ID | Brand | Publication | Hyperlink Present | Verification Status |")
            content.append("|---|---|---|---|---|")
            for m in mentions:
                content.append(
                    f"| `{m.get('id')}` | {m.get('brand')} | [{m.get('domain')}]({m.get('url')}) | "
                    f"**{m.get('has_hyperlink')}** | {m.get('verification_status')} |"
                )
        else:
            content.append("*No new brand mentions detected in monitored feeds.*")

        content.extend([
            "",
            "## 3. Backlink Verification Status",
        ])

        if backlinks:
            content.append("| Source URL | Target | Link Status | Anchor Text | Rel |")
            content.append("|---|---|---|---|---|")
            for b in backlinks:
                content.append(
                    f"| [{b.get('source_url')[:45]}...]({b.get('source_url')}) | "
                    f"{b.get('target_url')} | **{b.get('link_status')}** | "
                    f"\"{b.get('anchor_text')}\" | `{b.get('rel_attributes')}` |"
                )
        else:
            content.append("*No backlink URLs scheduled for check.*")

        content.extend([
            "",
            "## 4. Pending Outreach Drafts",
        ])

        if outreach_drafts:
            content.append("| Draft ID | Publication | Proposed Subject | Approval Status | Target URL |")
            content.append("|---|---|---|---|---|")
            for d in outreach_drafts:
                content.append(
                    f"| `{d.get('id')}` | {d.get('publication')} | {d.get('proposed_subject')} | "
                    f"**{d.get('approval_status')}** | [Inspect Target]({d.get('target_url')}) |"
                )
        else:
            content.append("*No outreach drafts generated.*")

        report_text = "\n".join(content)
        file_path = os.path.join(self.reports_dir, f"daily-report-{today_str}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        logger.info(f"Daily report saved to {file_path}")
        return file_path

    def generate_weekly_report(
        self,
        citations: List[Dict[str, Any]],
        competitor_opps: List[Dict[str, Any]],
        backlinks: List[Dict[str, Any]]
    ) -> str:
        """Generate structured Weekly Off-Page SEO Audit & Citations Report."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        correct_citations = [c for c in citations if c.get("nap_status") == "Verified Correct"]
        mismatched_citations = [c for c in citations if c.get("nap_status") == "Correction Needed"]

        content = [
            f"# IA Spaces - Weekly Off-Page & Citation Report ({today_str})",
            f"*Generated at: {timestamp} IST*",
            "",
            "## Weekly Executive Summary",
            f"- **Total Hub Citations Monitored:** {len(citations)}",
            f"- **Verified Correct Listings:** {len(correct_citations)}",
            f"- **Listings Requiring NAP Correction:** {len(mismatched_citations)}",
            f"- **Competitor Editorial Angle Prospects:** {len(competitor_opps)}",
            f"- **Active Monitored Backlinks:** {len(backlinks)}",
            "",
            "---",
            "",
            "## 1. Hub Citation Audit (NAP Consistency)",
        ]

        if citations:
            content.append("| Hub Name | Directory | NAP Status | Correction Required |")
            content.append("|---|---|---|---|")
            for c in citations:
                content.append(
                    f"| **{c.get('hub_name')}** | [{c.get('directory_name')}]({c.get('listing_url')}) | "
                    f"**{c.get('nap_status')}** | {c.get('correction_required')} |"
                )
        else:
            content.append("*No citations loaded for auditing.*")

        content.extend([
            "",
            "## 2. Competitor Coverage Gaps",
        ])

        if competitor_opps:
            content.append("| Publication | Competitor | Editorial Angle | Competitor Linked? |")
            content.append("|---|---|---|---|")
            for cp in competitor_opps:
                content.append(
                    f"| [{cp.get('publication')}]({cp.get('source_url')}) | {cp.get('competitor')} | "
                    f"**{cp.get('editorial_angle')}** | {cp.get('competitor_linked')} |"
                )
        else:
            content.append("*No competitor coverage identified in weekly sample.*")

        report_text = "\n".join(content)
        file_path = os.path.join(self.reports_dir, f"weekly-report-{today_str}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        logger.info(f"Weekly report saved to {file_path}")
        return file_path
