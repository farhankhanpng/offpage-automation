"""Markdown report generator for the daily and weekly pipelines (reports/).

Every report opens with a Run Health section, so a run where fetches failed or the
Sheet was not reachable can't be mistaken for a quiet day.
"""

import os
from typing import Any, Dict, List

from ..utils.logger import get_logger
from ..utils.time_utils import now_ist_str, today_ist_str

logger = get_logger("ReportGenerator")


def _cell(value: Any, limit: int = 0) -> str:
    text = "" if value is None else str(value)
    text = text.replace("|", "\\|").replace("\n", " ")
    return text[:limit] + "..." if limit and len(text) > limit else text


class ReportGenerator:
    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    @staticmethod
    def _health_section(health, sheets_status: str) -> List[str]:
        if health is None:
            return []
        lines = [
            "## Run Health",
            f"- **Status:** {health.status()}",
            f"- **Checks:** {health.summary_line()}",
            f"- **Google Sheets:** {sheets_status}",
        ]
        for issue in health.issues:
            lines.append(f"- **Issue:** {issue.replace('REQUIRED: ', '')}")
        if health.failures:
            lines += ["", "<details><summary>Failed checks ({})</summary>".format(len(health.failures)), "",
                      "| Check | URL / query | Reason |", "|---|---|---|"]
            for f in health.failures[:50]:
                lines.append(f"| {_cell(f['source'])} | {_cell(f['url'], 90)} | {_cell(f['detail'], 90)} |")
            lines += ["", "</details>"]
        lines += ["", "---", ""]
        return lines

    def _write(self, filename: str, content: List[str]) -> str:
        path = os.path.join(self.reports_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")
        logger.info(f"Report saved to {path}")
        return path

    def generate_daily_report(
        self,
        opportunities: List[Dict[str, Any]],
        mentions: List[Dict[str, Any]],
        backlinks: List[Dict[str, Any]],
        outreach_drafts: List[Dict[str, Any]],
        health=None,
        sheets_status: str = "",
        label: str = "",
    ) -> str:
        today = today_ist_str()
        unlinked = [m for m in mentions if m.get("is_unlinked")]
        live = [b for b in backlinks if str(b.get("link_status", "")).startswith("Live")]
        missing = [b for b in backlinks if b.get("link_status") == "Missing"]
        unverified_bl = [b for b in backlinks if b.get("link_status") == "Could Not Verify"]
        ranked = sorted(opportunities, key=lambda o: o.get("opportunity_score", 0), reverse=True)
        top = [o for o in ranked if o.get("priority") in ("High", "Medium")]

        c = [
            f"# IA Spaces - Daily Off-Page SEO Report ({today}){label}",
            f"*Generated at: {now_ist_str()} IST*",
            "",
        ]
        c += self._health_section(health, sheets_status)
        c += [
            "## Summary",
            f"- **Candidates checked:** {len(opportunities)} "
            f"({sum(1 for o in opportunities if o.get('page_fetched') == 'Yes')} pages fetched)",
            f"- **High/Medium opportunities:** {len(top)}",
            f"- **Brand mentions found:** {len(mentions)} ({len(unlinked)} with no link to iaspaces.co)",
            f"- **Backlink sources:** {len(backlinks)} ({len(live)} live, {len(missing)} missing, "
            f"{len(unverified_bl)} could not be verified)",
            f"- **Outreach drafts created:** {len(outreach_drafts)} (all *Pending Approval* - nothing is sent)",
            "",
            "## 1. Top Opportunities",
        ]
        if top:
            c += ["| ID | Publication | Page | Score | Priority | Breakdown |", "|---|---|---|---|---|---|"]
            for o in top[:15]:
                c.append(f"| `{o.get('id')}` | {_cell(o.get('publication'))} | "
                         f"[{_cell(o.get('page_title') or 'Link', 70)}]({o.get('url')}) | "
                         f"**{o.get('opportunity_score')}/100** | {o.get('priority')} | {_cell(o.get('scoring_breakdown'))} |")
        else:
            c.append("*No High/Medium opportunities in this run.*")

        c += ["", "## 2. Brand Mentions"]
        if mentions:
            c += ["| Brand | Page | Link to iaspaces.co |", "|---|---|---|"]
            for m in mentions:
                c.append(f"| {_cell(m.get('brand'))} | [{_cell(m.get('page_title') or m.get('domain'), 70)}]"
                         f"({m.get('mentioned_url')}) | **{_cell(m.get('has_hyperlink'))}** |")
        else:
            c.append("*No brand mentions found on the pages that could be fetched.*")

        c += ["", "## 3. Backlink Verification"]
        if backlinks:
            c += ["| Source URL | Status | Anchor | Rel | Notes |", "|---|---|---|---|---|"]
            for b in backlinks:
                c.append(f"| {_cell(b.get('source_url'), 60)} | **{_cell(b.get('link_status'))}** | "
                         f"{_cell(b.get('anchor_text'))} | {_cell(b.get('rel_attributes'))} | {_cell(b.get('notes'), 140)} |")
        else:
            c.append("*No backlink sources configured.*")

        c += ["", "## 4. Outreach Drafts (Pending Approval)"]
        if outreach_drafts:
            c += ["| Draft ID | Publication | Subject | Contact | Target |", "|---|---|---|---|---|"]
            for d in outreach_drafts:
                c.append(f"| `{d.get('id')}` | {_cell(d.get('publication'))} | {_cell(d.get('proposed_subject'))} | "
                         f"{_cell(d.get('contact_email'))} | [page]({d.get('target_url')}) |")
            c += ["", "> Before approving: open the page, check the contact, and confirm every figure in the draft."]
        else:
            c.append("*No drafts created.*")

        return self._write(f"daily-report-{today}.md", c)

    def generate_weekly_report(
        self,
        citations: List[Dict[str, Any]],
        competitor_opps: List[Dict[str, Any]],
        backlinks: List[Dict[str, Any]],
        health=None,
        sheets_status: str = "",
        label: str = "",
    ) -> str:
        today = today_ist_str()
        by_status: Dict[str, int] = {}
        for ci in citations:
            by_status[ci.get("nap_status", "")] = by_status.get(ci.get("nap_status", ""), 0) + 1

        c = [
            f"# IA Spaces - Weekly Off-Page & Citation Report ({today}){label}",
            f"*Generated at: {now_ist_str()} IST*",
            "",
        ]
        c += self._health_section(health, sheets_status)
        c += ["## Summary", f"- **Directory listings checked:** {len(citations)}"]
        for status, n in sorted(by_status.items()):
            c.append(f"  - {status}: {n}")
        c += [
            f"- **Competitor coverage rows (from fetched pages only):** {len(competitor_opps)}",
            f"- **Backlink sources checked:** {len(backlinks)}",
            "",
            "## 1. Directory Listings vs Master NAP",
        ]
        if citations:
            c += ["| Hub | Directory | Status | Action |", "|---|---|---|---|"]
            for ci in citations:
                link = f"[{_cell(ci.get('directory_name'))}]({ci.get('listing_url')})" if ci.get("listing_url") \
                    else _cell(ci.get("directory_name"))
                c.append(f"| **{_cell(ci.get('hub_name'))}** | {link} | **{_cell(ci.get('nap_status'))}** | "
                         f"{_cell(ci.get('correction_required') or ci.get('notes'), 140)} |")
        else:
            c.append("*No listings configured in data/citations_seed.csv.*")

        c += ["", "## 2. Competitor Coverage"]
        if competitor_opps:
            c += ["| Publication | Competitor | Angle | Competitor linked? |", "|---|---|---|---|"]
            for cp in competitor_opps:
                c.append(f"| [{_cell(cp.get('publication'))}]({cp.get('source_url')}) | {_cell(cp.get('competitor'))} | "
                         f"{_cell(cp.get('editorial_angle'))} | {_cell(cp.get('competitor_linked'))} |")
        else:
            c.append("*No competitor coverage found on pages that could be fetched.*")

        c += ["", "## 3. Backlink Verification"]
        if backlinks:
            c += ["| Source URL | Status | Notes |", "|---|---|---|"]
            for b in backlinks:
                c.append(f"| {_cell(b.get('source_url'), 60)} | **{_cell(b.get('link_status'))}** | {_cell(b.get('notes'), 140)} |")
        else:
            c.append("*No backlink sources configured.*")

        return self._write(f"weekly-report-{today}.md", c)
