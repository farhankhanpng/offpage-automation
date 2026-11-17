"""Citation & Local Directory Tracker for IA Spaces hubs.

For each directory listing in data/citations_seed.csv the tracker FETCHES the live
listing page and checks it against the canonical master NAP (data/ia-spaces-nap-master.csv):
  - phone: the master phone's last 10 digits appear on the page;
  - PIN code: the hub's postal code appears on the page;
  - website: the page links to (or mentions) iaspaces.co.

Statuses:
  "Matches Master NAP"        - every available check passed on the live page;
  "Correction Needed"         - the page loaded but at least one check failed;
  "Could Not Verify"          - the page could not be fetched (blocked / error) -> check by hand;
  "Placeholder URL"           - the seed URL is a placeholder; replace it with the real listing;
  "Unknown Hub"               - hub_name does not match a Business Name in the master NAP.
It never submits or edits listings.
"""

import csv
import os
import re
from typing import Any, Dict, Optional

from ..utils.fetcher import PoliteFetcher
from ..utils.html_parser import parse_html_content
from ..utils.logger import get_logger
from ..utils.time_utils import now_ist_str
from ..utils.url_utils import extract_domain, generate_stable_id, normalize_url

logger = get_logger("CitationTracker")

PLACEHOLDER_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (r"PXX", r"placeholder", r"example\.com", r"TODO")]


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


class CitationTracker:
    def __init__(self, master_nap_csv: Optional[str] = None, fetcher: Optional[PoliteFetcher] = None):
        self.master_hubs: Dict[str, Dict[str, str]] = {}
        self.fetcher = fetcher
        if master_nap_csv and os.path.exists(master_nap_csv):
            self.load_master_nap(master_nap_csv)

    def load_master_nap(self, csv_path: str):
        try:
            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    hub = (row.get("Business Name") or "").strip()
                    if not hub:
                        continue
                    self.master_hubs[hub.lower()] = {
                        "hub_name": hub,
                        "city": (row.get("City") or "").strip(),
                        "address": " ".join(filter(None, [row.get("Address Line 1", ""), row.get("Address Line 2", "")])).strip(),
                        "phone": (row.get("Primary Phone") or "").strip(),
                        "website_url": (row.get("Website") or "").strip(),
                        "pin_code": (row.get("Postal Code") or "").strip(),
                    }
            logger.info(f"Loaded {len(self.master_hubs)} hub records from master NAP.")
        except Exception as e:
            logger.warning(f"Could not load master NAP from {csv_path}: {e}")

    @staticmethod
    def is_placeholder(url: str) -> bool:
        return not url or any(p.search(url) for p in PLACEHOLDER_PATTERNS)

    def audit_listing(self, directory_name: str, listing_url: str, hub_name: str, **_ignored) -> Dict[str, Any]:
        master = self.master_hubs.get((hub_name or "").lower().strip())
        record: Dict[str, Any] = {
            "id": generate_stable_id(f"{directory_name}::{hub_name}", prefix="CIT"),
            "directory_name": directory_name,
            "listing_url": normalize_url(listing_url) if listing_url else "",
            "hub_name": hub_name,
            "address": master["address"] if master else "",
            "phone": master["phone"] if master else "",
            "website_url": master["website_url"] if master else "",
            "nap_status": "Not Checked",
            "last_checked": now_ist_str(),
            "correction_required": "",
            "notes": "Address/Phone/Website columns show the canonical master NAP values.",
        }

        if not master:
            record.update(nap_status="Unknown Hub",
                          notes=f"Hub '{hub_name}' is not a Business Name in the master NAP file.")
            return record

        if self.is_placeholder(listing_url):
            record.update(nap_status="Placeholder URL",
                          correction_required="Replace with the real listing URL in data/citations_seed.csv")
            return record

        if self.fetcher is None:
            record.update(nap_status="Could Not Verify", notes="No fetcher configured.")
            return record

        res = self.fetcher.fetch(listing_url, source="citation check")
        if not res.get("ok"):
            record.update(
                nap_status="Could Not Verify",
                correction_required="Check this listing by hand",
                notes=f"Listing could not be fetched ({res.get('status')}). Directories often block bots.",
            )
            return record

        parsed = parse_html_content(res["html"], base_url=listing_url)
        page_text = f"{parsed.get('title', '')} {parsed.get('body_text', '')}"
        page_digits = _digits(page_text + " " + res["html"])
        problems, passed = [], []

        phone10 = _digits(master["phone"])[-10:]
        if phone10:
            (passed if phone10 in page_digits else problems).append(
                "phone" if phone10 in page_digits else f"Phone {master['phone']} not shown on listing"
            )
        if master["pin_code"]:
            (passed if master["pin_code"] in page_text else problems).append(
                "PIN" if master["pin_code"] in page_text else f"PIN code {master['pin_code']} not shown on listing"
            )
        links_site = any(extract_domain(lk.get("href", "")) in ("iaspaces.co", "www.iaspaces.co")
                         for lk in parsed.get("links", []))
        if links_site or "iaspaces.co" in page_text.lower():
            passed.append("website")
        else:
            problems.append("No link to iaspaces.co on listing")

        if problems:
            record.update(nap_status="Correction Needed", correction_required="; ".join(problems),
                          notes=f"Passed: {', '.join(passed) or 'none'}")
        else:
            record.update(nap_status="Matches Master NAP", correction_required="None",
                          notes="Phone, PIN code and website found on the live listing.")
        return record
