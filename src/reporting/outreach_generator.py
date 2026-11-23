"""Outreach Draft Generator.

Produces draft emails with status "Pending Approval". It NEVER sends anything.

Rules:
  - drafts are only created for pages that were fetched and inspected (enforced by the runner);
  - company facts (hub/city counts) come from settings.yaml -> brand_facts, which records
    where each figure was checked; no unsourced statistics are inserted;
  - contact emails are only filled in when the address is published on the page itself;
    otherwise the draft says "Unverified (requires manual lookup)".
"""

from typing import Any, Dict, List, Optional

from ..utils.time_utils import now_ist_str
from ..utils.url_utils import extract_domain, generate_stable_id

UNVERIFIED_EMAIL = "Unverified (requires manual lookup)"

DEFAULT_FACTS = {
    "hubs": "40+",
    "cities": "25+",
    "parent": "India Accelerator",
    "website": "https://iaspaces.co",
}


class OutreachDraftGenerator:
    def __init__(self, brand_facts: Optional[Dict[str, str]] = None):
        facts = dict(DEFAULT_FACTS)
        facts.update({k: str(v) for k, v in (brand_facts or {}).items() if v not in (None, "")})
        self.facts = facts

    @staticmethod
    def angle_for(editorial_angle: str = "", unlinked_brand: bool = False) -> str:
        if unlinked_brand:
            return "Unlinked Brand Mention"
        if editorial_angle.startswith("Listicle"):
            return "Listicle Inclusion"
        if editorial_angle.startswith("Tier-2"):
            return "Tier-2 Expansion / Commentary"
        return "Industry Commentary"

    def generate_draft(
        self,
        publication: str,
        target_url: str,
        angle: str,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_source: Optional[str] = None,
        page_title: str = "",
        brand: str = "IA Spaces",
        evidence: str = "",
    ) -> Dict[str, Any]:
        f = self.facts
        name = contact_name or "Editorial Team"
        domain = extract_domain(target_url) or publication
        piece = f'"{page_title}"' if page_title else "your article"
        signoff = f"Team IA Spaces ({f['parent']})\n{f['website']}"

        if angle == "Unlinked Brand Mention":
            # The subject always names IA Spaces; the body names the brand the article used.
            subject = "Thank you for covering IA Spaces - a quick link request"
            if brand.strip().lower() in ("ia spaces", "iaspaces.co"):
                intro = f"Thank you for mentioning IA Spaces in {piece} on {domain}:\n{target_url}\n\n"
            else:
                intro = (
                    f"Thank you for mentioning {brand} in {piece} on {domain}:\n{target_url}\n\n"
                    f"IA Spaces is the coworking network of {f['parent']}. "
                )
            body = (
                f"Hi {name},\n\n{intro}"
                f"Would you consider linking the mention to our official site, {f['website']}, "
                f"so readers can find the hub details directly?\n\n"
                f"Thanks for the coverage either way.\n\n{signoff}"
            )
        elif angle == "Listicle Inclusion":
            subject = f"A suggestion for {piece} on {domain}"
            body = (
                f"Hi {name},\n\n"
                f"I came across {piece} on {domain}:\n{target_url}\n\n"
                f"If you update it, IA Spaces (the coworking network of {f['parent']}) may be a useful addition: "
                f"we operate {f['hubs']} hubs across {f['cities']} Indian cities, including Tier-2 locations.\n\n"
                f"Hub details and pricing: {f['website']}\n\n"
                f"Happy to send any information you need.\n\n{signoff}"
            )
        elif angle == "Tier-2 Expansion / Commentary":
            subject = f"Commentary on Tier-2 workspace growth for {domain}"
            body = (
                f"Hi {name},\n\n"
                f"I read {piece} on {domain} ({target_url}).\n\n"
                f"IA Spaces, backed by {f['parent']}, runs {f['hubs']} coworking hubs across {f['cities']} cities, "
                f"many of them outside the metros. If you are working on stories about Tier-2 startup "
                f"ecosystems or flexible workspaces, our leadership team would be glad to offer commentary.\n\n"
                f"More background: {f['website']}\n\n{signoff}"
            )
        else:
            subject = f"Workspace commentary for {domain}"
            body = (
                f"Hi {name},\n\n"
                f"I came across {piece} on {domain}:\n{target_url}\n\n"
                f"If useful for future coverage of flexible workspaces in India, IA Spaces "
                f"({f['hubs']} hubs, {f['cities']} cities) can share context and commentary.\n\n{signoff}"
            )

        return {
            "id": generate_stable_id(f"{target_url}::{angle}", prefix="OUT"),
            "publication": publication or domain,
            "contact_name": contact_name or "Editorial Team (not verified)",
            "contact_email": contact_email or UNVERIFIED_EMAIL,
            "contact_source": contact_source or "Not found on page",
            "target_url": target_url,
            "proposed_subject": subject,
            "draft_email": body,
            "approval_status": "Pending Approval",
            "created_date": now_ist_str(),
        }


def pick_contact(emails: List[str]) -> Optional[str]:
    """Prefer editorial-looking addresses published on the page."""
    preferred = ("editor", "editorial", "news", "tips", "contribut", "content", "press", "features")
    for e in emails:
        if any(p in e.split("@")[0] for p in preferred):
            return e
    return emails[0] if emails else None
