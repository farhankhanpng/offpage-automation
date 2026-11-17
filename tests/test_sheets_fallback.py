"""Unit tests for Google Sheets offline local CSV cache fallback and row deduplication.
"""

import unittest
import os
import sys
import shutil

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.sheets.sheets_client import GoogleSheetsClient


class TestSheetsFallback(unittest.TestCase):

    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "temp_offline_cache")
        os.makedirs(self.test_dir, exist_ok=True)
        # Point to a non-existent credentials file so it exercises the offline fallback cleanly
        self.client = GoogleSheetsClient(
            credentials_path="non_existent_creds.json",
            offline_dir=self.test_dir
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sync_tab_creates_offline_csv(self):
        records = [
            {
                "id": "OPP-001",
                "publication": "Inc42",
                "url": "https://inc42.com/features/coworking",
                "page_title": "Coworking Feature",
                "discovery_date": "2026-03-01",
                "source": "RSS",
                "opportunity_score": 85,
                "priority": "High",
                "scoring_breakdown": "CRE: 25, India: 20"
            }
        ]
        count = self.client.sync_tab("Opportunities", records, key_field="ID")
        self.assertEqual(count, 1)

        csv_file = os.path.join(self.test_dir, "opportunities.csv")
        self.assertTrue(os.path.exists(csv_file))

        with open(csv_file, mode="r", encoding="utf-8-sig") as f:
            content = f.read()
            self.assertIn("OPP-001", content)
            self.assertIn("Inc42", content)
            self.assertIn("https://inc42.com/features/coworking", content)

    def test_deduplication_updates_existing_record(self):
        records1 = [{"id": "BL-001", "source_url": "https://site.com/a", "link_status": "Missing"}]
        self.client.sync_tab("Backlinks", records1, key_field="ID")

        # Second run updates status of same ID
        records2 = [{"id": "BL-001", "source_url": "https://site.com/a", "link_status": "Live (Dofollow)"}]
        count = self.client.sync_tab("Backlinks", records2, key_field="ID")
        self.assertEqual(count, 1)

        csv_file = os.path.join(self.test_dir, "backlinks.csv")
        with open(csv_file, mode="r", encoding="utf-8-sig") as f:
            content = f.read()
            self.assertIn("Live (Dofollow)", content)
            self.assertNotIn("Missing", content)


if __name__ == "__main__":
    unittest.main()
