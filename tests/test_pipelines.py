"""End-to-end tests of the daily and weekly runners with fake fetchers (no network)."""

import csv
import os
import shutil
import sys
import tempfile
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from run_daily import run_daily_pipeline  # noqa: E402
from run_weekly import run_weekly_pipeline  # noqa: E402
from src.citations.citation_tracker import CitationTracker  # noqa: E402
from tests.test_sheets_fallback import FakeSpreadsheet  # noqa: E402

NAP = os.path.join(BASE_DIR, "data", "ia-spaces-nap-master.csv")


class FailingFetcher:
    """Every page fails, as when a site blocks bots or the network is down."""
    health = None

    def fetch(self, url, source="page"):
        if self.health is not None:
            self.health.record(source, False, url=url, detail="HTTP 403")
        return {"ok": False, "status": "HTTP 403", "http_code": 403, "html": "", "final_url": url,
                "error": "HTTP Error 403", "robots_blocked": False}


class PageFetcher(FailingFetcher):
    def __init__(self, pages):
        self.pages = pages

    def fetch(self, url, source="page"):
        html = self.pages.get(url)
        if html is None:
            return super().fetch(url, source)
        if self.health is not None:
            self.health.record(source, True, url=url)
        return {"ok": True, "status": "Success", "http_code": 200, "html": html, "final_url": url,
                "error": "", "robots_blocked": False}


def make_project():
    """Temporary copy of config/ and data/ seeds so runs never touch the real cache."""
    tmp = tempfile.mkdtemp()
    shutil.copytree(os.path.join(BASE_DIR, "config"), os.path.join(tmp, "config"))
    os.makedirs(os.path.join(tmp, "data"))
    for name in ("backlinks_seed.csv", "citations_seed.csv", "competitors_seed.csv",
                 "mentions_seed.csv", "ia-spaces-nap-master.csv", "purged_ids.txt"):
        shutil.copy(os.path.join(BASE_DIR, "data", name), os.path.join(tmp, "data", name))
    return tmp


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class TestPipelines(unittest.TestCase):

    def setUp(self):
        self.base = make_project()
        os.environ.pop("REQUIRE_SHEETS", None)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_weekly_never_fabricates_competitor_rows(self):
        result = run_weekly_pipeline(base_dir=self.base, fetcher=FailingFetcher())
        self.assertEqual(result["competitors"], [])
        statuses = {c["nap_status"] for c in result["citations"]}
        self.assertTrue(statuses <= {"Could Not Verify", "Placeholder URL", "No Listing Found"})
        self.assertEqual(result["health"].exit_code(), 2)
        self.assertEqual(read(os.path.join(self.base, "data", "sheets_offline_cache", "competitors.csv")), [])

    def test_first_run_removes_legacy_v1_rows_from_every_tab(self):
        cache = os.path.join(self.base, "data", "sheets_offline_cache")
        os.makedirs(cache)
        with open(os.path.join(cache, "competitors.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["ID", "Competitor", "Competitor Linked"])
            w.writerow(["COMP-E50FEA", "Awfis / Smartworks", "Yes"])  # fabricated v1.0 fallback row
        run_weekly_pipeline(base_dir=self.base, fetcher=FailingFetcher())
        self.assertEqual(read(os.path.join(cache, "competitors.csv")), [])

    def test_daily_drafts_nothing_when_pages_cannot_be_read(self):
        result = run_daily_pipeline(base_dir=self.base, use_feeds=False, fetcher=FailingFetcher())
        self.assertEqual(result["drafts"], [])
        self.assertTrue(all(o["page_fetched"].startswith("No") for o in result["opportunities"]))
        self.assertTrue(all(b["link_status"] == "Could Not Verify" for b in result["backlinks"]))
        self.assertEqual(result["health"].status(), "Failing")
        dash = {r["Metric"]: r["Value"] for r in read(os.path.join(self.base, "data", "sheets_offline_cache", "dashboard.csv"))}
        self.assertTrue(dash["System Status"].startswith("Failing"))

    def test_dry_run_writes_only_to_dry_run_folders(self):
        run_daily_pipeline(dry_run=True, base_dir=self.base)
        run_weekly_pipeline(dry_run=True, base_dir=self.base)
        self.assertFalse(os.path.exists(os.path.join(self.base, "data", "sheets_offline_cache")))
        self.assertTrue(os.listdir(os.path.join(self.base, "data", "dry_run_cache")))
        self.assertTrue(os.listdir(os.path.join(self.base, "reports", "dry-run")))

    def test_ids_are_stable_between_runs(self):
        a = run_daily_pipeline(dry_run=True, base_dir=self.base)
        b = run_daily_pipeline(dry_run=True, base_dir=self.base)
        self.assertEqual([o["id"] for o in a["opportunities"]], [o["id"] for o in b["opportunities"]])
        rows = read(os.path.join(self.base, "data", "dry_run_cache", "opportunities.csv"))
        self.assertEqual(len(rows), len({r["ID"] for r in rows}))

    def test_unlinked_mention_produces_reclamation_draft_with_page_contact(self):
        url = "https://india.entrepreneur.com/news-and-trends/india-accelerator-acquires-mysoho-to-expand-ia-spaces/497405"
        html = ("<html><head><title>India Accelerator Acquires MySOHO to Expand IA Spaces</title></head><body>"
                "<p>The deal expands IA Spaces nationwide.</p><a href='mailto:editor@entrepreneur.com'>Editor</a></body></html>")
        result = run_daily_pipeline(base_dir=self.base, use_feeds=False, fetcher=PageFetcher({url: html}))
        drafts = [d for d in result["drafts"] if d["target_url"] == url]
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["contact_email"], "editor@entrepreneur.com")
        self.assertIn("IA Spaces", drafts[0]["proposed_subject"])
        self.assertNotIn("40% YoY", drafts[0]["draft_email"])

    def test_mysoho_article_draft_names_ia_spaces_not_mysoho(self):
        url = "https://www.devdiscourse.com/article/business/3636320-india-accelerators-pioneering-mysoho-acquisition-a-new-era-for-co-working-spaces"
        html = ("<html><head><title>India Accelerator's MySOHO Acquisition: A New Era for Co-Working Spaces</title></head>"
                "<body><p>India Accelerator has acquired co-working company MySOHO.</p></body></html>")
        result = run_daily_pipeline(base_dir=self.base, use_feeds=False, fetcher=PageFetcher({url: html}))
        drafts = [d for d in result["drafts"] if d["target_url"] == url]
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["proposed_subject"], "Thank you for covering IA Spaces - a quick link request")
        self.assertIn("Thank you for mentioning India Accelerator", drafts[0]["draft_email"])
        self.assertIn("IA Spaces is the coworking network of India Accelerator", drafts[0]["draft_email"])

    def test_daily_news_roundups_get_no_draft(self):
        from run_daily import is_digest_page
        self.assertTrue(is_digest_page("Startup news and updates: Daily roundup (November 20, 2026)"))
        self.assertTrue(is_digest_page("Indian Listed New-Age Tech Company Tracker: Market Cap"))
        self.assertFalse(is_digest_page("The Top 10 Best Coworking Spaces in Gurgaon"))

    def test_india_accelerator_funding_story_gets_no_link_request(self):
        from run_daily import pick_unlinked
        mentions = [{"brand": "India Accelerator", "is_unlinked": True, "pitchable": False}]
        self.assertIsNone(pick_unlinked(mentions))

    def test_backlink_to_legacy_parent_page_is_flagged(self):
        html = "<html><body><a href='https://www.indiaaccelerator.co/ia-spaces/'>IA Spaces</a></body></html>"
        result = run_daily_pipeline(base_dir=self.base, use_feeds=False, fetcher=PageFetcher({"https://www.indiaaccelerator.co/": html}))
        home = next(b for b in result["backlinks"] if b["source_url"] == "https://www.indiaaccelerator.co/")
        self.assertEqual(home["link_status"], "Missing")
        self.assertIn("legacy page", home["notes"])

    def test_required_sheets_connection_fails_the_run(self):
        os.environ["REQUIRE_SHEETS"] = "true"
        try:
            result = run_weekly_pipeline(base_dir=self.base, fetcher=PageFetcher({}))
            self.assertIn(result["health"].exit_code(), (1, 2))
            self.assertTrue(any(i.startswith("REQUIRED:") for i in result["health"].issues))
        finally:
            os.environ.pop("REQUIRE_SHEETS", None)

    def test_connected_run_writes_to_the_sheet(self):
        book = FakeSpreadsheet()
        run_weekly_pipeline(base_dir=self.base, fetcher=FailingFetcher(), spreadsheet=book)
        values = book.sheets["Citations"].values
        self.assertGreater(len(values), 1)


class TestCitationTracker(unittest.TestCase):

    def setUp(self):
        self.page = ("<html><body><p>IA Spaces - MGF Metropolis Mall, MG Road, Gurugram 122002. "
                     "Call +91 80313 22007</p><a href='https://iaspaces.co/gurgaon/mg-road/'>Website</a></body></html>")

    def test_matching_listing(self):
        t = CitationTracker(NAP, fetcher=PageFetcher({"https://dir.example/ia": self.page}))
        r = t.audit_listing("Dir", "https://dir.example/ia", "IA Spaces - MG Road, Gurugram")
        self.assertEqual(r["nap_status"], "Matches Master NAP")

    def test_mismatched_listing(self):
        page = self.page.replace("122002", "110001").replace("22007", "99999")
        t = CitationTracker(NAP, fetcher=PageFetcher({"https://dir.example/ia": page}))
        r = t.audit_listing("Dir", "https://dir.example/ia", "IA Spaces - MG Road, Gurugram")
        self.assertEqual(r["nap_status"], "Correction Needed")
        self.assertIn("PIN code 122002", r["correction_required"])

    def test_listing_with_old_brand_name_needs_correction(self):
        page = self.page.replace("IA Spaces - MGF Metropolis Mall", "India Accelerator - MG Road")
        t = CitationTracker(NAP, fetcher=PageFetcher({"https://dir.example/ia": page}))
        r = t.audit_listing("Dir", "https://dir.example/ia", "IA Spaces - MG Road, Gurugram")
        self.assertEqual(r["nap_status"], "Correction Needed")
        self.assertIn("IA Spaces", r["correction_required"])

    def test_missing_listing(self):
        t = CitationTracker(NAP, fetcher=FailingFetcher())
        r = t.audit_listing("Justdial", "", "IA Spaces - MG Road, Gurugram")
        self.assertEqual(r["nap_status"], "No Listing Found")

    def test_placeholder_and_unknown_hub(self):
        t = CitationTracker(NAP, fetcher=FailingFetcher())
        self.assertEqual(t.audit_listing("Justdial", "https://www.justdial.com/x/011PXX11",
                                         "IA Spaces - MG Road, Gurugram")["nap_status"], "Placeholder URL")
        self.assertEqual(t.audit_listing("Dir", "https://dir.example/a", "Unknown Hub")["nap_status"], "Unknown Hub")


if __name__ == "__main__":
    unittest.main()
