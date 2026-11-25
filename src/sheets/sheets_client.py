"""Google Sheets sync client (gspread) with a local CSV cache.

How a sync works (per tab):
  1. Start from the local CSV cache (data/sheets_offline_cache/<tab>.csv).
  2. If connected, read the live Sheet tab and merge it in:
       - rows that exist only in the Sheet (e.g. written by the other runner,
         GitHub Actions vs. a local run) are kept;
       - "human" columns (Approval Status, Team Notes) are taken from the Sheet,
         so edits your team makes in the Sheet are never overwritten.
  3. Upsert this run's records by ID: machine columns are refreshed, human
     columns keep their existing value (new rows get the default, e.g.
     "Pending Approval").
  4. Drop rows listed in data/purged_ids.txt (tombstones) and rows not seen for
     `retention_days` that nobody has annotated.
  5. Write the cache, then write the Sheet: grow the grid if needed, write all
     rows, and clear any leftover rows below.

Never exposes credentials in logs or exceptions.
"""

import csv
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Set

from ..utils.logger import get_logger
from ..utils.time_utils import now_ist, now_ist_str, parse_timestamp

logger = get_logger("SheetsClient")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    # Needed only to find the spreadsheet by name; set sheets.sheet_id to avoid it.
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

SHEET_HEADERS: Dict[str, List[str]] = {
    "Dashboard": ["Metric", "Value", "Last Updated"],
    "Opportunities": [
        "ID", "Publication", "URL", "Page Title", "Discovery Date", "Source",
        "Page Fetched", "Opportunity Score", "Priority", "Scoring Breakdown",
        "Last Seen", "Team Notes",
    ],
    "Backlinks": [
        "ID", "Source URL", "Target URL", "HTTP Status", "Link Exists",
        "Anchor Text", "Rel Attributes", "Link Status", "Last Checked", "Notes",
        "Last Seen", "Team Notes",
    ],
    "Brand_Mentions": [
        "ID", "Brand", "Mentioned URL", "Page Title", "Domain",
        "Discovery Date", "Context", "Has Hyperlink", "Link Destination",
        "Anchor Text", "Verification Status", "Source", "Last Seen", "Team Notes",
    ],
    "Competitors": [
        "ID", "Publication", "Competitor", "Source URL", "Page Title",
        "Competitor Linked", "Competitor Link URL", "Editorial Angle",
        "Discovery Date", "Evidence", "Last Seen", "Team Notes",
    ],
    "Outreach": [
        "ID", "Publication", "Contact Name", "Contact Email", "Contact Source",
        "Target URL", "Proposed Subject", "Draft Email", "Approval Status",
        "Created Date", "Last Seen", "Team Notes",
    ],
    "Citations": [
        "ID", "Directory Name", "Listing URL", "Hub Name", "Address",
        "Phone", "Website URL", "NAP Status", "Last Checked", "Correction Required",
        "Notes", "Last Seen", "Team Notes",
    ],
    "Activity_Log": ["Timestamp", "Action", "Status", "Details"],
}

# Columns owned by people. The pipeline never overwrites a non-empty value here.
HUMAN_COLUMNS: Dict[str, List[str]] = {
    "Outreach": ["Approval Status", "Team Notes"],
}
DEFAULT_HUMAN_COLUMNS = ["Team Notes"]
HUMAN_DEFAULTS = {"Approval Status": "Pending Approval"}

# Tabs keyed by a metric name: merged by key, never pruned, no human columns.
SNAPSHOT_TABS = {"Dashboard"}


def _snake(header: str) -> str:
    return header.lower().replace(" ", "_")


def human_columns_for(tab: str) -> List[str]:
    if tab in SNAPSHOT_TABS or tab == "Activity_Log":
        return []
    return HUMAN_COLUMNS.get(tab, DEFAULT_HUMAN_COLUMNS)


def load_tombstones(path: Optional[str]) -> Set[str]:
    """IDs listed (one per line, '#' comments allowed) in purged_ids.txt."""
    ids: Set[str] = set()
    if not path or not os.path.exists(path):
        return ids
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                ids.add(line)
    return ids


def _with_retry(fn, *args, attempts: int = 4, **kwargs):
    """Call a gspread function, retrying on quota (429) and server (5xx) errors."""
    delay = 2.0
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # gspread.exceptions.APIError carries .response
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (429, 500, 502, 503) and i < attempts - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise


def _col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class GoogleSheetsClient:
    """Synchronises tabs with Google Sheets, keeping a local CSV cache."""

    def __init__(
        self,
        credentials_path: str = "secrets/google-service-account.json",
        sheet_name: str = "IA Spaces - Off-Page SEO Master",
        sheet_url: Optional[str] = None,
        offline_dir: str = "data/sheets_offline_cache",
        sheet_id: Optional[str] = None,
        offline_only: bool = False,
        tombstones_path: Optional[str] = None,
        retention_days: int = 90,
        spreadsheet=None,
    ):
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.sheet_url = sheet_url
        self.sheet_id = sheet_id
        self.offline_dir = offline_dir
        self.offline_only = offline_only
        self.tombstones_path = tombstones_path
        self.retention_days = retention_days
        self.spreadsheet = spreadsheet  # injectable for tests
        self.is_connected = spreadsheet is not None
        self.connection_error = ""
        self._activity_buffer: List[List[str]] = []

        os.makedirs(self.offline_dir, exist_ok=True)
        if not offline_only and spreadsheet is None:
            self._initialize_client()
        if self.is_connected:
            self._ensure_sheets()

    # ------------------------------------------------------------------ connect
    def _initialize_client(self):
        env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if env_json and not os.path.exists(self.credentials_path):
            try:
                os.makedirs(os.path.dirname(self.credentials_path) or ".", exist_ok=True)
                with open(self.credentials_path, "w", encoding="utf-8") as f:
                    f.write(env_json)
                logger.info("Restored credentials from GOOGLE_SERVICE_ACCOUNT_JSON.")
            except OSError as e:
                logger.warning(f"Could not write credentials from environment: {e.__class__.__name__}")

        if not os.path.exists(self.credentials_path):
            self.connection_error = "service account JSON not found"
            logger.info("Service account JSON not found. Running in offline / local cache mode.")
            return

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            self.connection_error = "gspread / google-auth not installed"
            logger.warning("gspread or google-auth not installed. Using local cache only.")
            return

        try:
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
            gc = gspread.authorize(creds)
            if self.sheet_id:
                self.spreadsheet = gc.open_by_key(self.sheet_id)
            elif self.sheet_url:
                self.spreadsheet = gc.open_by_url(self.sheet_url)
            else:
                self.spreadsheet = gc.open(self.sheet_name)
            self.is_connected = True
            logger.info(f"Connected to Google Spreadsheet: '{self.spreadsheet.title}'")
        except Exception as e:
            self.connection_error = f"{e.__class__.__name__}: {str(e)[:200]}"
            logger.warning(
                f"Could not open spreadsheet '{self.sheet_name}'. Check it exists, is shared with the "
                f"service account email (Editor), or set sheets.sheet_id. Details: {self.connection_error}"
            )

    def _ensure_sheets(self):
        try:
            existing = {ws.title for ws in self.spreadsheet.worksheets()}
        except Exception as e:
            logger.warning(f"Could not list worksheets: {e.__class__.__name__}")
            return
        for title, headers in SHEET_HEADERS.items():
            if title in existing:
                continue
            try:
                ws = _with_retry(self.spreadsheet.add_worksheet, title=title, rows=200, cols=len(headers) + 2)
                _with_retry(ws.update, values=[headers], range_name="A1")
            except Exception as e:
                logger.warning(f"Failed to create worksheet '{title}': {e.__class__.__name__}")

    # --------------------------------------------------------------- local io
    def _cache_path(self, tab_name: str) -> str:
        return os.path.join(self.offline_dir, f"{tab_name.lower()}.csv")

    def _read_cache(self, tab_name: str, key_field: str) -> Dict[str, Dict[str, str]]:
        rows: Dict[str, Dict[str, str]] = {}
        path = self._cache_path(tab_name)
        if not os.path.exists(path):
            return rows
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    k = (r.get(key_field) or "").strip()
                    if k:
                        rows[k] = {h: (r.get(h) or "") for h in SHEET_HEADERS[tab_name]}
        except Exception as e:
            logger.warning(f"Could not read local cache for {tab_name}: {e}")
        return rows

    def _write_cache(self, tab_name: str, rows: Iterable[Dict[str, str]]):
        path = self._cache_path(tab_name)
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=SHEET_HEADERS[tab_name], extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        except Exception as e:
            logger.warning(f"Error writing local cache for {tab_name}: {e}")

    # -------------------------------------------------------------- sheet io
    def _read_sheet(self, ws, tab_name: str, key_field: str) -> Dict[str, Dict[str, str]]:
        values = _with_retry(ws.get_all_values)
        rows: Dict[str, Dict[str, str]] = {}
        if not values:
            return rows
        header = [h.strip() for h in values[0]]
        if key_field not in header:
            return rows
        for raw in values[1:]:
            row = {header[i]: raw[i] if i < len(raw) else "" for i in range(len(header))}
            k = (row.get(key_field) or "").strip()
            if k:
                rows[k] = {h: row.get(h, "") for h in SHEET_HEADERS[tab_name]}
        self._last_sheet_row_count = len(values)
        return rows

    def _write_sheet(self, ws, tab_name: str, rows: List[Dict[str, str]], previous_rows: int):
        headers = SHEET_HEADERS[tab_name]
        data = [headers] + [[r.get(h, "") for h in headers] for r in rows]
        need_rows, need_cols = len(data) + 1, len(headers)
        try:
            if getattr(ws, "row_count", need_rows) < need_rows or getattr(ws, "col_count", need_cols) < need_cols:
                _with_retry(ws.resize, rows=max(need_rows, getattr(ws, "row_count", 0)),
                            cols=max(need_cols, getattr(ws, "col_count", 0)))
        except Exception as e:
            logger.warning(f"Could not resize '{tab_name}': {e.__class__.__name__}")
        _with_retry(ws.update, values=data, range_name="A1")
        if previous_rows > len(data):
            last_col = _col_letter(max(need_cols, getattr(ws, "col_count", need_cols)))
            _with_retry(ws.batch_clear, [f"A{len(data) + 1}:{last_col}{previous_rows}"])

    # ------------------------------------------------------------------ sync
    def _record_to_row(self, tab_name: str, rec: Dict[str, Any]) -> Dict[str, str]:
        row = {}
        for h in SHEET_HEADERS[tab_name]:
            val = rec.get(h)
            if val is None:
                val = rec.get(_snake(h))
            row[h] = "" if val is None else str(val)
        return row

    @staticmethod
    def _annotated(row: Dict[str, str], human_cols: List[str]) -> bool:
        for col in human_cols:
            value = (row.get(col) or "").strip()
            if value and value != HUMAN_DEFAULTS.get(col):
                return True
        return False

    def _should_drop(self, row: Dict[str, str], human_cols: List[str]) -> bool:
        """Drop un-annotated rows that are legacy (no 'Last Seen': written before v1.1,
        when dry-run fixtures and placeholder rows leaked into the data) or stale."""
        if self._annotated(row, human_cols):
            return False
        seen = parse_timestamp(row.get("Last Seen", ""))
        if not seen:
            return True
        return self.retention_days > 0 and (now_ist() - seen).days > self.retention_days

    def sync_tab(self, tab_name: str, records: List[Dict[str, Any]], key_field: str = "ID",
                 refresh_fn=None) -> int:
        """Merge records into the tab (cache + Sheet). Returns the number of rows kept.

        refresh_fn(row) may return updated machine columns for rows this run did not
        produce (used to rewrite older outreach drafts on the current template). It never
        changes human columns or "Last Seen"."""
        if tab_name not in SHEET_HEADERS:
            logger.error(f"Unknown tab name: {tab_name}")
            return 0
        headers = SHEET_HEADERS[tab_name]
        human_cols = human_columns_for(tab_name)
        tombstones = load_tombstones(self.tombstones_path)
        snapshot = tab_name in SNAPSHOT_TABS
        now_str = now_ist_str()

        rows: Dict[str, Dict[str, str]] = self._read_cache(tab_name, key_field)

        ws, previous_rows, sheet_ok = None, 0, False
        if self.is_connected:
            try:
                ws = self.spreadsheet.worksheet(tab_name)
                self._last_sheet_row_count = 0
                sheet_rows = self._read_sheet(ws, tab_name, key_field)
                previous_rows = self._last_sheet_row_count
                for k, srow in sheet_rows.items():
                    if k not in rows:
                        rows[k] = srow
                    else:
                        for col in human_cols:
                            if (srow.get(col) or "").strip():
                                rows[k][col] = srow[col]
                sheet_ok = True
            except Exception as e:
                logger.warning(f"Could not read Sheet tab '{tab_name}' ({e.__class__.__name__}); "
                               f"merging with local cache only.")

        for rec in records:
            new_row = self._record_to_row(tab_name, rec)
            k = new_row.get(key_field, "").strip()
            if not k:
                continue
            if "Last Seen" in headers:
                new_row["Last Seen"] = now_str
            existing = rows.get(k)
            for col in human_cols:
                kept = (existing or {}).get(col, "").strip()
                new_row[col] = kept or new_row.get(col, "").strip() or HUMAN_DEFAULTS.get(col, "")
            rows[k] = new_row

        if refresh_fn is not None:
            produced = {self._record_to_row(tab_name, rec).get(key_field, "").strip() for rec in records}
            for k, row in rows.items():
                if k in produced or k in tombstones:
                    continue
                try:
                    updates = refresh_fn(row) or {}
                except Exception as e:  # a bad old row must never break the sync
                    logger.warning(f"Could not refresh row {k} in '{tab_name}': {e.__class__.__name__}")
                    continue
                for col, val in updates.items():
                    if col in headers and col not in human_cols and col != "Last Seen":
                        row[col] = val

        final_rows = [
            r for k, r in rows.items()
            if k not in tombstones and (snapshot or not self._should_drop(r, human_cols))
        ]
        self._write_cache(tab_name, final_rows)

        if self.is_connected and ws is not None and sheet_ok:
            try:
                self._write_sheet(ws, tab_name, final_rows, previous_rows)
                logger.info(f"Synced {len(final_rows)} rows to Google Sheet tab '{tab_name}'.")
            except Exception as e:
                logger.warning(f"Failed to update Google Sheet tab '{tab_name}': {e.__class__.__name__}")
                self.log_activity("SYNC", "FAILED", f"Sheet write failed for '{tab_name}'")
                return len(final_rows)

        self.log_activity("SYNC", "SUCCESS", f"Synced {len(final_rows)} records to tab '{tab_name}'")
        return len(final_rows)

    # -------------------------------------------------------------- activity
    def log_activity(self, action: str, status: str, details: str):
        """Append to the local activity log now; Sheet rows are sent in one batch by flush()."""
        entry = [now_ist_str(), action, status, details]
        path = os.path.join(self.offline_dir, "activity_log.csv")
        try:
            exists = os.path.exists(path)
            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not exists:
                    writer.writerow(SHEET_HEADERS["Activity_Log"])
                writer.writerow(entry)
        except Exception:
            pass
        self._activity_buffer.append(entry)

    def flush(self):
        """Send buffered Activity_Log rows to the Sheet in a single API call."""
        if not (self.is_connected and self._activity_buffer):
            self._activity_buffer = []
            return
        try:
            ws = self.spreadsheet.worksheet("Activity_Log")
            _with_retry(ws.append_rows, self._activity_buffer, value_input_option="RAW")
        except Exception as e:
            logger.warning(f"Could not append Activity_Log rows: {e.__class__.__name__}")
        self._activity_buffer = []
