"""Tests for the Sheets client: local cache, merge with the live Sheet, team edits, purges."""

import csv
import os
import shutil
import sys
import tempfile
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.sheets.sheets_client import SHEET_HEADERS, GoogleSheetsClient  # noqa: E402


class FakeWorksheet:
    def __init__(self, title, values=None, rows=100, cols=26):
        self.title = title
        self.values = [list(r) for r in (values or [])]
        self.row_count, self.col_count = rows, cols
        self.cleared = []
        self.appended = []

    def get_all_values(self):
        return [list(r) for r in self.values]

    def update(self, values=None, range_name="A1", **_):
        for i, row in enumerate(values):
            while len(self.values) <= i:
                self.values.append([])
            self.values[i] = list(row)

    def resize(self, rows=None, cols=None):
        self.row_count = rows or self.row_count
        self.col_count = cols or self.col_count

    def batch_clear(self, ranges):
        self.cleared.extend(ranges)
        start = int(ranges[0].split(":")[0][1:])
        self.values = self.values[: start - 1]

    def append_rows(self, rows, **_):
        self.appended.extend(rows)


class FakeSpreadsheet:
    title = "Fake"

    def __init__(self):
        self.sheets = {}

    def worksheets(self):
        return list(self.sheets.values())

    def add_worksheet(self, title, rows, cols):
        self.sheets[title] = FakeWorksheet(title, rows=rows, cols=cols)
        return self.sheets[title]

    def worksheet(self, title):
        return self.sheets[title]


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class TestSheetsOffline(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.client = GoogleSheetsClient(credentials_path="non_existent_creds.json", offline_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_tab_creates_offline_csv(self):
        records = [{"id": "OPP-001", "publication": "Inc42", "url": "https://inc42.com/features/coworking",
                    "page_title": "Coworking Feature", "opportunity_score": 85, "priority": "High"}]
        self.assertEqual(self.client.sync_tab("Opportunities", records), 1)
        rows = read_csv(os.path.join(self.test_dir, "opportunities.csv"))
        self.assertEqual(rows[0]["ID"], "OPP-001")
        self.assertEqual(rows[0]["Page Title"], "Coworking Feature")
        self.assertTrue(rows[0]["Last Seen"])

    def test_deduplication_updates_existing_record(self):
        self.client.sync_tab("Backlinks", [{"id": "BL-001", "source_url": "https://site.com/a", "link_status": "Missing"}])
        count = self.client.sync_tab("Backlinks", [{"id": "BL-001", "source_url": "https://site.com/a",
                                                    "link_status": "Live (Followed)"}])
        self.assertEqual(count, 1)
        rows = read_csv(os.path.join(self.test_dir, "backlinks.csv"))
        self.assertEqual(rows[0]["Link Status"], "Live (Followed)")

    def test_legacy_rows_without_last_seen_are_dropped(self):
        path = os.path.join(self.test_dir, "backlinks.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["ID", "Source URL", "Link Status", "Notes"])
            w.writerow(["BL-7A8B9C0D", "https://indiaaccelerator.co/ecosystem", "Live (Dofollow)", "fixture"])
        self.client.sync_tab("Backlinks", [{"id": "BL-NEW", "source_url": "https://x.com", "link_status": "Missing"}])
        ids = [r["ID"] for r in read_csv(path)]
        self.assertEqual(ids, ["BL-NEW"])

    def test_tombstoned_ids_are_removed_and_never_return(self):
        tomb = os.path.join(self.test_dir, "purged.txt")
        with open(tomb, "w") as f:
            f.write("BL-BAD   # bad row\n")
        client = GoogleSheetsClient(credentials_path="none.json", offline_dir=self.test_dir, tombstones_path=tomb)
        client.sync_tab("Backlinks", [{"id": "BL-BAD", "source_url": "https://bad"}, {"id": "BL-OK", "source_url": "https://ok"}])
        ids = [r["ID"] for r in read_csv(os.path.join(self.test_dir, "backlinks.csv"))]
        self.assertEqual(ids, ["BL-OK"])


class TestSheetsMerge(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.book = FakeSpreadsheet()
        self.client = GoogleSheetsClient(offline_dir=self.test_dir, spreadsheet=self.book)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _draft(self, i="OUT-1", subject="Subject v1"):
        return {"id": i, "publication": "inc42.com", "target_url": "https://inc42.com/x",
                "proposed_subject": subject, "draft_email": "Hi", "approval_status": "Pending Approval"}

    def test_creates_all_tabs_with_headers(self):
        self.assertEqual(set(self.book.sheets), set(SHEET_HEADERS))
        self.assertEqual(self.book.sheets["Outreach"].values[0], SHEET_HEADERS["Outreach"])

    def test_team_edits_in_sheet_survive_the_next_run(self):
        self.client.sync_tab("Outreach", [self._draft()])
        ws = self.book.sheets["Outreach"]
        header = ws.values[0]
        ws.values[1][header.index("Approval Status")] = "Approved"
        ws.values[1][header.index("Team Notes")] = "Send Monday"

        self.client.sync_tab("Outreach", [self._draft(subject="Subject v2")])
        row = dict(zip(ws.values[0], ws.values[1]))
        self.assertEqual(row["Approval Status"], "Approved")
        self.assertEqual(row["Team Notes"], "Send Monday")
        self.assertEqual(row["Proposed Subject"], "Subject v2")  # machine column refreshed

    def test_rows_only_in_sheet_are_kept(self):
        self.client.sync_tab("Backlinks", [{"id": "BL-A", "source_url": "https://a"}])
        # simulate the other runner (e.g. GitHub Actions) having written BL-B to the Sheet
        ws = self.book.sheets["Backlinks"]
        other = dict.fromkeys(SHEET_HEADERS["Backlinks"], "")
        other.update({"ID": "BL-B", "Source URL": "https://b", "Last Seen": ws.values[1][SHEET_HEADERS["Backlinks"].index("Last Seen")]})
        ws.values.append([other[h] for h in SHEET_HEADERS["Backlinks"]])

        fresh = GoogleSheetsClient(offline_dir=tempfile.mkdtemp(), spreadsheet=self.book)
        fresh.sync_tab("Backlinks", [{"id": "BL-C", "source_url": "https://c"}])
        ids = [r[0] for r in ws.values[1:]]
        self.assertEqual(sorted(ids), ["BL-A", "BL-B", "BL-C"])

    def test_grid_grows_and_leftover_rows_are_cleared(self):
        ws = self.book.sheets["Backlinks"]
        ws.row_count = 3
        self.client.sync_tab("Backlinks", [{"id": f"BL-{i}", "source_url": f"https://{i}"} for i in range(5)])
        self.assertGreaterEqual(ws.row_count, 6)
        # purge three rows, then confirm the Sheet shrinks instead of keeping stale rows
        tomb = os.path.join(self.test_dir, "p.txt")
        with open(tomb, "w") as f:
            f.write("BL-0\nBL-1\nBL-2\n")
        self.client.tombstones_path = tomb
        self.client.sync_tab("Backlinks", [])
        self.assertEqual(len(ws.values), 3)  # header + 2
        self.assertTrue(ws.cleared)

    def test_activity_log_is_sent_in_one_batch(self):
        self.client.sync_tab("Backlinks", [{"id": "BL-A"}])
        self.client.sync_tab("Citations", [{"id": "CIT-A"}])
        self.client.flush()
        self.assertEqual(len(self.book.sheets["Activity_Log"].appended), 2)


if __name__ == "__main__":
    unittest.main()
