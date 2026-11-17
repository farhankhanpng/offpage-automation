"""Citation & Local Directory Tracker for IA Spaces hubs.
Compares directory listings against verified hub NAP master data without auto-submitting.
Enforces strict 1-to-1 hub address/phone pairing — never cross-pollinates hub details.
"""

import csv
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger
from ..utils.url_utils import normalize_url, generate_stable_id

logger = get_logger("CitationTracker")


class CitationTracker:
    """Manages and audits directory listings across IA Spaces regional hubs."""

    def __init__(self, master_nap_csv: Optional[str] = None):
        self.master_hubs: Dict[str, Dict[str, str]] = {}
        if master_nap_csv and os.path.exists(master_nap_csv):
            self.load_master_nap(master_nap_csv)

    def load_master_nap(self, csv_path: str):
        """Load official NAP records for all 15 IA Spaces hubs from verified CSV."""
        try:
            with open(csv_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    hub_name = (row.get("Business Name") or row.get("hub_name", "")).strip()
                    addr = " ".join(filter(None, [row.get("Address Line 1", ""), row.get("Address Line 2", ""), row.get("address", "")])).strip()
                    phone = (row.get("Primary Phone") or row.get("phone", "")).strip()
                    website = (row.get("Website") or row.get("website_url", "")).strip()
                    pin = (row.get("Postal Code") or row.get("pin_code", "")).strip()

                    if hub_name:
                        self.master_hubs[hub_name.lower()] = {
                            "hub_name": hub_name,
                            "city": row.get("City") or row.get("city", "").strip(),
                            "address": addr,
                            "phone": phone,
                            "website_url": website,
                            "pin_code": pin
                        }
            logger.info(f"Loaded {len(self.master_hubs)} verified hub records from master NAP.")
        except Exception as e:
            logger.warning(f"Could not load master NAP from {csv_path}: {e}")

    def audit_listing(
        self,
        directory_name: str,
        listing_url: str,
        hub_name: str,
        found_address: str,
        found_phone: str,
        found_website: str
    ) -> Dict[str, Any]:
        """Audit a single directory listing against the canonical master NAP."""
        clean_hub_key = hub_name.lower().strip()
        master = self.master_hubs.get(clean_hub_key)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record: Dict[str, Any] = {
            "id": generate_stable_id(f"{directory_name}::{hub_name}", prefix="CIT"),
            "directory_name": directory_name,
            "listing_url": normalize_url(listing_url),
            "hub_name": hub_name,
            "address": found_address,
            "phone": found_phone,
            "website_url": found_website,
            "nap_status": "Not Verified",
            "last_checked": now_str,
            "correction_required": "None",
            "notes": ""
        }

        if not master:
            record["notes"] = f"Hub '{hub_name}' not found in canonical master NAP database."
            record["nap_status"] = "Unknown Hub"
            return record

        corrections = []

        # Check Phone
        clean_found_phone = "".join(filter(str.isdigit, found_phone))
        clean_master_phone = "".join(filter(str.isdigit, master["phone"]))
        if clean_master_phone and clean_found_phone != clean_master_phone:
            corrections.append(f"Phone mismatch: found '{found_phone}', expected '{master['phone']}'")

        # Check Website
        if normalize_url(found_website) != normalize_url(master["website_url"]):
            corrections.append(f"Website URL mismatch: found '{found_website}', expected '{master['website_url']}'")

        # Check PIN code / address
        if master.get("pin_code") and master["pin_code"] not in found_address:
            corrections.append(f"Address missing verified PIN code ({master['pin_code']})")

        if not corrections:
            record["nap_status"] = "Verified Correct"
            record["correction_required"] = "None"
        else:
            record["nap_status"] = "Correction Needed"
            record["correction_required"] = "; ".join(corrections)

        return record
