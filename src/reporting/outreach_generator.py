"""Outreach Draft Generator.

Produces structured, professional draft emails with status "Pending Approval".
It NEVER sends anything.

Rules:
  - drafts are only created for pages that were fetched and inspected (enforced by the runner);
  - company facts (hub/city counts, spokesperson) come from settings.yaml -> brand_facts,
    which records where each figure was checked; no unsourced statistics are inserted;
  - the services listed are the ones named on the iaspaces.co homepage (checked 2026-11-23);
  - hub names, areas and hub-page links come from the master hub file
    (data/ia-spaces-nap-master.csv), the same file the citation check uses;
  - contact emails are only filled in when the address is published on the page itself;
    otherwise the draft says "Unverified (requires manual lookup)".
"""

import re
from typing import Any, Dict, List, Optional

from ..utils.time_utils import now_ist_str
from ..utils.url_utils import extract_domain, generate_stable_id

UNVERIFIED_EMAIL = "Unverified (requires manual lookup)"

DEFAULT_FACTS = {
    "hubs": "40+",
    "cities": "25+",
    "parent": "India Accelerator",
    "website": "https://iaspaces.co",
    "phone": "+91 80313 22007",
    "spokesperson": "Ashish Bhatia",
    "spokesperson_title": "Founder & CEO, India Accelerator",
}

DEFAULT_SENDER = {"name": "", "title": "", "email": "info@iaspaces.co"}

# Spellings used in articles -> the city name used in the hub file
CITY_ALIASES = {
    "gurgaon": "Gurugram", "gurugram": "Gurugram", "bombay": "Mumbai", "vizag": "Visakhapatnam",
}

MAX_HUBS_LISTED = 6


def _hub_short_name(business_name: str) -> str:
    """'IA Spaces - MG Road, Gurugram' -> 'MG Road'."""
    name = re.sub(r"^\s*IA Spaces\s*-\s*", "", business_name or "")
    return name.rsplit(",", 1)[0].strip()


class OutreachDraftGenerator:
    def __init__(self, brand_facts: Optional[Dict[str, str]] = None,
                 hubs: Optional[List[Dict[str, str]]] = None,
                 sender: Optional[Dict[str, str]] = None):
        facts = dict(DEFAULT_FACTS)
        facts.update({k: str(v) for k, v in (brand_facts or {}).items() if v not in (None, "")})
        self.facts = facts
        snd = dict(DEFAULT_SENDER)
        snd.update({k: str(v) for k, v in (sender or {}).items() if v not in (None, "")})
        self.sender = snd
        self.hubs = [h for h in (hubs or []) if h.get("City") and h.get("Business Name")]

    # ---------- helpers ----------

    @staticmethod
    def angle_for(editorial_angle: str = "", unlinked_brand: bool = False) -> str:
        if unlinked_brand:
            return "Unlinked Brand Mention"
        if editorial_angle.startswith("Listicle"):
            return "Listicle Inclusion"
        if editorial_angle.startswith("Tier-2"):
            return "Tier-2 Expansion / Commentary"
        return "Industry Commentary"

    def _cities_in(self, text: str) -> List[str]:
        """Hub-file cities named in the text (whole words, in hub-file order)."""
        t = (text or "").lower()
        found: List[str] = []
        known = {h["City"] for h in self.hubs}
        candidates = {c.lower(): c for c in known}
        candidates.update({k: v for k, v in CITY_ALIASES.items() if v in known})
        for word, city in candidates.items():
            if re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", t) and city not in found:
                found.append(city)
        return found

    def _hubs_in(self, city: str) -> List[Dict[str, str]]:
        return [h for h in self.hubs if h["City"] == city]

    def _hub_lines(self, city: str) -> str:
        lines = []
        for h in self._hubs_in(city)[:MAX_HUBS_LISTED]:
            area = (h.get("Address Line 2") or "").strip()
            label = _hub_short_name(h["Business Name"])
            where = f" ({area})" if area else ""
            lines.append(f"  - IA Spaces {label}{where}: {h.get('Website', '').strip()}")
        return "\n".join(lines)

    def _signature(self) -> str:
        f, s = self.facts, self.sender
        contact = [f["website"]]
        if s["email"]:
            contact.append(s["email"])
        if f.get("phone"):
            contact.append(f["phone"])
        return "\n".join([
            "Warm regards,",
            "",
            s["name"] or "XXX",
            s["title"] or "Marketing Manager",
            f"IA Spaces, the coworking network of {f['parent']}",
            " | ".join(contact),
        ])

    @staticmethod
    def _greeting(contact_name: Optional[str]) -> str:
        name = (contact_name or "").strip()
        if not name or "not verified" in name.lower() or name.lower() == "editorial team":
            return "Dear Editor,"
        return f"Dear {name},"

    def _intro(self) -> str:
        s = self.sender
        name = s["name"] or "XXX"
        title = s["title"] or "Marketing Manager"
        return f"My name is {name}, and I am the {title} at IA Spaces."

    def _offer_block(self) -> str:
        f = self.facts
        return (
            "What IA Spaces offers:\n"
            "  - Dedicated desks, private cabins, private suites and fully managed office spaces\n"
            "  - Virtual office: a business address for registration and mail\n"
            "  - Private meeting rooms, plus events and workshops for members\n"
            f"  - Depending on plan and eligibility, access to {f['parent']}'s mentors, "
            "investor network and accelerator programmes"
        )

    @staticmethod
    def _connect_ask() -> str:
        return ("I would also be very grateful for a chance to connect, in whatever way suits you "
                "best (a short call, a video meeting, or a visit to one of our hubs), to tell you "
                "more about IA Spaces in detail and to understand how we could be useful to you and "
                "your readers.")

    def _about(self) -> str:
        f = self.facts
        return (f"We are the coworking and managed-office network of {f['parent']}, "
                f"with {f['hubs']} hubs across {f['cities']} Indian cities, from metros such as "
                f"Gurugram, Noida and Mumbai to growing cities such as Chandigarh, Surat and Jaipur.")

    # ---------- drafts ----------

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
        domain = extract_domain(target_url) or publication
        title = (page_title or "").strip()
        piece = f'"{title}"' if title else "your recent article"
        greeting = self._greeting(contact_name)
        cities = self._cities_in(f"{title} {evidence}")
        signature = self._signature()

        intro = self._intro()
        offer = self._offer_block()
        connect = self._connect_ask()

        if angle == "Unlinked Brand Mention":
            subject = (f"Thank you for covering IA Spaces in {piece}" if title
                       else "Thank you for covering IA Spaces")
            if brand.strip().lower() in ("ia spaces", "iaspaces.co"):
                who = ""
            else:
                who = (f"The article refers to {brand}; IA Spaces is the coworking network of "
                       f"{f['parent']}, so the hubs it describes are ours. ")
            target = f["website"]
            city_hubs = [h for c in cities for h in self._hubs_in(c)]
            if len(city_hubs) == 1:
                target = city_hubs[0].get("Website", "").strip() or target
            body = (
                f"{greeting}\n\n"
                f"I hope you are doing well. {intro}\n\n"
                f"I wanted to sincerely thank you for covering us in {piece} on {domain}:\n{target_url}\n\n"
                f"{who}We are grateful for the coverage, and I hope you will not mind a small request. "
                f"The article mentions us but does not link to our website. If it is possible, would you "
                f"kindly consider linking the words \"IA Spaces\" (or \"{brand}\") to {target}? It "
                f"would help your readers find the hub and its details easily.\n\n"
                f"I would also be grateful if you could include IA Spaces by name in this article, "
                f"so readers know where to find us.\n\n"
                f"{connect}\n\n"
                f"Thank you once again for your time and for writing about us.\n\n{signature}"
            )

        elif angle == "Listicle Inclusion":
            city = cities[0] if cities else ""
            hub_lines = self._hub_lines(city) if city else ""
            n = len(self._hubs_in(city)) if city else 0
            count = f"{n} hub{'s' if n != 1 else ''} in {city}"
            subject = (f"A humble request to include IA Spaces in {piece}" if title
                       else "A humble request to include IA Spaces in your list")
            hubs_block = (f"We currently have {count}:\n{hub_lines}\n\n" if hub_lines else "")
            body = (
                f"{greeting}\n\n"
                f"I hope you are doing well. {intro}\n\n"
                f"I recently came across {piece} on {domain} and found it genuinely useful:\n{target_url}\n\n"
                f"I would like to briefly introduce IA Spaces. {self._about()}\n\n"
                f"{hubs_block}"
                f"{offer}\n\n"
                f"I would be grateful if you could include IA Spaces in this article. I would be happy to send "
                f"a short write-up for the entry, hub photos and contact details for each location, so it "
                f"takes as little of your time as possible.\n\n"
                f"{connect}\n\n"
                f"Thank you for your time and consideration.\n\n{signature}"
            )

        elif angle == "Tier-2 Expansion / Commentary":
            subject = f"Introducing IA Spaces: a possible resource for {domain} on workspaces beyond the metros"
            body = (
                f"{greeting}\n\n"
                f"I hope you are doing well. {intro}\n\n"
                f"I read {piece} on {domain} with great interest:\n{target_url}\n\n"
                f"I would like to briefly introduce IA Spaces. {self._about()}\n\n"
                f"{offer}\n\n"
                f"I would be grateful if you could include IA Spaces in this article, or in your future "
                f"stories on startup ecosystems and flexible workspaces outside the metros. "
                f"{f['spokesperson']}, {f['spokesperson_title']}, would also be glad to share his views on:\n"
                f"  - why startups and enterprise teams are choosing flexible offices in Tier-2 cities\n"
                f"  - how an accelerator-backed workspace network supports early-stage founders\n"
                f"  - what operators need to get right when opening outside the metros\n\n"
                f"{connect}\n\n"
                f"Thank you for your time and consideration.\n\n{signature}"
            )

        else:  # Industry Commentary
            subject = f"Introducing IA Spaces: a possible resource for {domain} on flexible workspaces"
            body = (
                f"{greeting}\n\n"
                f"I hope you are doing well. {intro}\n\n"
                f"I came across {piece} on {domain} and enjoyed reading it:\n{target_url}\n\n"
                f"I would like to briefly introduce IA Spaces. {self._about()}\n\n"
                f"{offer}\n\n"
                f"I would be grateful if you could include IA Spaces in this article, or in your future "
                f"coverage of coworking, managed offices and flexible workspaces in India. "
                f"{f['spokesperson']}, {f['spokesperson_title']}, would also be glad to share his views on:\n"
                f"  - demand for flexible and managed offices from startups and enterprises\n"
                f"  - growth of workspace demand in Tier-2 cities\n"
                f"  - how founders choose a workspace at each stage of growth\n\n"
                f"{connect}\n\n"
                f"Thank you for your time and consideration.\n\n{signature}"
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
