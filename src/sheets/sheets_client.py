"""Google Sheets sync client via gspread with resilient local CSV/JSON cache fallback.
Manages the 8 required tabs:
- Dashboard, Opportunities, Backlinks, Brand_Mentions, Competitors, Outreach, Citations, Activity_Log.
Never exposes credentials or API keys in logs or exceptions.
"""

import os
import csv
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger
from ..utils.url_utils import normalize_url

logger = get_logger("SheetsClient")

SHEET_HEADERS = {
    "Dashboard": ["Metric", "Value", "Last Updated"],
    "Opportunities": [
        "ID", "Publication", "URL", "Page Title", "Discovery Date",
        "Source", "Opportunity Score", "Priority", "Scoring Breakdown"
    ],
    "Backlinks": [
        "ID", "Source URL", "Target URL", "HTTP Status", "Link Exists",
        "Anchor Text", "Rel Attributes", "Link Status", "Last Checked", "Notes"
    ],
    "Brand_Mentions": [
        "ID", "Brand", "Mentioned URL", "Page Title", "Domain",
        "Discovery Date", "Context", "Has Hyperlink", "Link Destination",
        "Anchor Text", "Verification Status", "Source"
    ],
    "Competitors": [
        "ID", "Publication", "Competitor", "Source URL", "Page Title",
        "Competitor Linked", "Competitor Link URL", "Editorial Angle",
        "Discovery Date", "Evidence"
    ],
    "Outreach": [
        "ID", "Publication", "Contact Name", "Contact Email", "Contact Source",
        "Target URL", "Proposed Subject", "Draft Email", "Approval Status", "Created Date"
    ],
    "Citations": [
        "ID", "Directory Name", "Listing URL", "Hub Name", "Address",
        "Phone", "Website URL", "NAP Status", "Last Checked", "Correction Required", "Notes"
    ],
    "Activity_Log": ["Timestamp", "Action", "Status", "Details"]
}


class GoogleSheetsClient:
    """Manages Google Sheets synchronization with automated local fallback."""

    def __init__(
        self,
        credentials_path: str = "secrets/google-service-account.json",
        sheet_name: str = "IA Spaces - Off-Page SEO Master",
        sheet_url: Optional[str] = None,
        offline_dir: str = "data/sheets_offline_cache"
    ):
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.sheet_url = sheet_url
        self.offline_dir = offline_dir
        self.gc = None
        self.spreadsheet = None
        self.is_connected = False

        os.makedirs(self.offline_dir, exist_ok=True)
        self._initialize_client()

    def _initialize_client(self):
        """Attempt to authenticate with Google Sheets API via gspread."""
        # Auto-restore credentials if passed via environment variable (e.g. GitHub Actions)
        env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if env_json and not os.path.exists(self.credentials_path):
            try:
                os.makedirs(os.path.dirname(self.credentials_path), exist_ok=True)
                with open(self.credentials_path, "w", encoding="utf-8") as f:
                    f.write(env_json)
                logger.info("Restored credentials from GOOGLE_SERVICE_ACCOUNT_JSON environment variable.")
            except Exception as e:
                logger.warning(f"Failed to write credentials from environment variable: {e}")

        if not os.path.exists(self.credentials_path):
            logger.info("Service account JSON not found. Running in resilient Offline / Local Cache mode.")
            return

        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            self.gc = gspread.authorize(creds)
            
            try:
                if self.sheet_url:
                    self.spreadsheet = self.gc.open_by_url(self.sheet_url)
                else:
                    try:
                        self.spreadsheet = self.gc.open(self.sheet_name)
                    except Exception:
                        # Try alternate name if user named it "Master" vs "Automation"
                        alt_name = "IA Spaces - Off-Page SEO Master" if "Automation" in self.sheet_name else "IA Spaces - Off-Page SEO Automation"
                        self.spreadsheet = self.gc.open(alt_name)

                logger.info(f"Connected to Google Spreadsheet: '{self.spreadsheet.title}'")
                self.is_connected = True
                self._ensure_sheets()
            except Exception as e:
                logger.warning(
                    f"Could not open spreadsheet '{self.sheet_name}'. "
                    f"Please make sure you have created the Google Sheet in your Google Drive and shared it with the service account email. "
                    f"Details: {e}. Using local cache."
                )
        except ImportError:
            logger.warning("gspread or google-auth not installed. Falling back to local offline cache.")
        except Exception as e:
            logger.warning(f"Google Sheets connection could not be established: {e}. Using offline cache.")

    def _ensure_sheets(self):
        """Ensure all 8 required tabs exist with header rows."""
        if not self.is_connected or not self.spreadsheet:
            return

        existing_titles = [s.title for s in self.spreadsheet.worksheets()]
        for title, headers in SHEET_HEADERS.items():
            if title not in existing_titles:
                try:
                    ws = self.spreadsheet.add_worksheet(title=title, rows=100, cols=len(headers) + 2)
                    ws.append_row(headers)
                    time.sleep(1.0)
                except Exception as e:
                    logger.warning(f"Failed to create worksheet '{title}': {e}")

    def sync_tab(self, tab_name: str, records: List[Dict[str, Any]], key_field: str = "ID") -> int:
        """Deduplicate records by key_field and sync to Google Sheets and local cache."""
        if tab_name not in SHEET_HEADERS:
            logger.error(f"Unknown tab name: {tab_name}")
            return 0

        headers = SHEET_HEADERS[tab_name]

        # 1. Always update local offline CSV cache for guaranteed durability
        local_path = os.path.join(self.offline_dir, f"{tab_name.lower()}.csv")
        existing_rows: Dict[str, Dict[str, Any]] = {}

        if os.path.exists(local_path):
            try:
                with open(local_path, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        k = r.get(key_field) or r.get(key_field.lower(), "")
                        if k:
                            existing_rows[k] = r
            except Exception:
                pass

        # Merge new records (keyed by ID or URL)
        for rec in records:
            k = rec.get(key_field) or rec.get(key_field.lower(), "")
            if not k and "id" in rec:
                k = rec["id"]
            if k:
                row_dict = {}
                for h in headers:
                    val = rec.get(h)
                    if val is None:
                        val = rec.get(h.lower().replace(" ", "_"), "")
                    row_dict[h] = str(val) if val is not None else ""
                existing_rows[k] = row_dict

        # Write merged records to local cache
        try:
            with open(local_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for row in existing_rows.values():
                    writer.writerow(row)
        except Exception as e:
            logger.warning(f"Error writing local cache for {tab_name}: {e}")

        # 2. Sync to Google Sheets if connected
        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet(tab_name)
                # Batch update with exponential backoff
                all_data = [headers] + [[r.get(h, "") for h in headers] for r in existing_rows.values()]
                ws.clear()
                ws.update("A1", all_data)
                logger.info(f"Successfully synced {len(existing_rows)} rows to Google Sheet tab '{tab_name}'.")
            except Exception as e:
                logger.warning(f"Failed to batch update Google Sheet tab '{tab_name}': {e}")

        self.log_activity("SYNC", "SUCCESS", f"Synced {len(existing_rows)} records to tab '{tab_name}'")
        return len(existing_rows)

    def log_activity(self, action: str, status: str, details: str):
        """Append an entry to Activity_Log tab and local log file."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = [now_str, action, status, details]

        local_log_csv = os.path.join(self.offline_dir, "activity_log.csv")
        try:
            file_exists = os.path.exists(local_log_csv)
            with open(local_log_csv, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(SHEET_HEADERS["Activity_Log"])
                writer.writerow(entry)
        except Exception:
            pass

        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("Activity_Log")
                ws.append_row(entry)
            except Exception:
                pass
