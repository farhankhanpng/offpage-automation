"""Outreach Draft Generator.

Produces structured, professional draft emails with status "Pending Approval".
It NEVER sends anything.

Rules:
  - drafts are only created for pages that were fetched and inspected (enforced by the runner);
  - company facts (hub/city counts, spokesperson) come from settings.yaml -> brand_facts,
    which records where each figure was checked; no unsourced statistics are inserted;
  - drafts follow the template approved by the Marketing Manager (2026-11-23): greeting,
    introduction, why we are writing, where IA Spaces is present, a few hubs in the article's
    city, the request, an offer of a call, and the signature. No facilities, prices or figures;
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
            s["name"] or "XXX",
            f"{s['title'] or 'Marketing Manager'} | IA Spaces",
            f"The Coworking & Managed Office Network of {f['parent']}",
            " | ".join(contact),
        ])

    @staticmethod
    def _greeting(contact_name: Optional[str]) -> str:
        name = (contact_name or "").strip()
        if not name or "not verified" in name.lower() or name.lower() == "editorial team":
            return "Hi Editor,"
        return f"Hi {name},"

    def _city_sample(self, first: str) -> str:
        """The article's city first, then the main cities (as in the approved template)."""
        preferred = ["Gurugram", "Mumbai", "Pune", "Ahmedabad", "Chandigarh", "Noida"]
        known = {h["City"] for h in self.hubs} or set(preferred)
        order = [first] + [c for c in preferred if c != first]
        cities = [c for c in order if c in known][:6]
        return ", ".join(cities)

    def _hub_list(self, city: str, limit: int = 4) -> str:
        return "\n".join(f"- IA Spaces {_hub_short_name(h['Business Name'])}: {h.get('Website', '').strip()}"
                          for h in self._hubs_in(city)[:limit])

    def _intro(self) -> str:
        s = self.sender
        name = s["name"] or "XXX"
        title = s["title"] or "Marketing Manager"
        return f"My name is {name}, and I am the {title} at IA Spaces."

    def _all_cities(self) -> List[str]:
        out: List[str] = []
        for h in self.hubs:
            if h["City"] not in out:
                out.append(h["City"])
        return out

    def _locations_block(self, cities: List[str]) -> str:
        """Where IA Spaces is present: the hubs in the article's city, then every city."""
        parts = []
        for city in cities[:1]:
            lines = self._hub_lines(city)
            if lines:
                n = len(self._hubs_in(city))
                parts.append(f"Our {'hubs' if n != 1 else 'hub'} in {city}:\n{lines}")
        all_cities = self._all_cities()
        if all_cities:
            parts.append("We are present in " + ", ".join(all_cities[:-1])
                         + (f" and {all_cities[-1]}." if len(all_cities) > 1 else f"{all_cities[0]}."))
        else:
            parts.append(f"Our locations are listed at {self.facts['website']}.")
        return "\n\n".join(parts)

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

        name = self.sender["name"] or "XXX"
        title_s = self.sender["title"] or "Marketing Manager"
        intro = (f"I'm {name}, {title_s} at IA Spaces, the coworking and managed office network "
                 f"of {f['parent']}.")
        city = cities[0] if cities else "Gurugram"
        offers = (f"IA Spaces offers flexible coworking and managed office solutions across multiple "
                  f"cities, including {self._city_sample(city)} and others. With a growing network of "
                  f"workspaces backed by the {f['parent']} ecosystem, we believe IA Spaces would be a "
                  f"relevant addition to your coverage.")
        hubs = self._hub_list(city)
        n_hubs = len(self._hubs_in(city))
        lead = (f"Here are a few of our {city} locations for reference:" if n_hubs > 1
                else f"Here is our {city} location for reference:")
        hubs_block = (f"{lead}\n\n{hubs}\n\n" if hubs else "")
        call = ("I'd also be happy to connect over a quick call to introduce the brand and explore "
                "potential editorial collaborations and other opportunities to work together.")
        closing = "Looking forward to hearing from you."
        article = f'"{title}"' if title else "your recent article"

        if angle == "Unlinked Brand Mention":
            subject = f"Thank you for featuring IA Spaces in {article}"
            target = f["website"]
            city_hubs = [h for c in cities for h in self._hubs_in(c)]
            if len(city_hubs) == 1:
                target = city_hubs[0].get("Website", "").strip() or target
            named = "IA Spaces" if brand.strip().lower() in ("ia spaces", "iaspaces.co") else brand
            reach = (f"I came across your article, {article}, and wanted to thank you for mentioning "
                     f"{named}, and to reach out to explore the possibility of linking it to our website.")
            ask = (f"We would appreciate it if you could consider mentioning IA Spaces by name in the "
                   f"article and linking it to {target}.")
        elif angle == "Listicle Inclusion":
            subject = f"Request to feature IA Spaces in {article}"
            reach = (f"I came across your article, {article}, and wanted to reach out to explore the "
                     f"possibility of featuring IA Spaces in the list.")
            ask = "We would appreciate it if you could consider including IA Spaces in the article."
        else:  # Industry Commentary and Tier-2 Expansion / Commentary
            subject = f"Request to feature IA Spaces in {article}"
            reach = (f"I came across your article, {article}, and wanted to reach out to explore the "
                     f"possibility of featuring IA Spaces in your coverage.")
            ask = ("We would appreciate it if you could consider including IA Spaces in the article "
                   "or in your future coverage of coworking and flexible workspaces.")

        body = (
            f"{greeting}\n\n"
            f"I hope you are doing well.\n\n"
            f"{intro}\n\n"
            f"{reach}\n\n"
            f"{offers}\n\n"
            f"{hubs_block}"
            f"{ask}\n\n"
            f"{call}\n\n"
            f"{closing}\n\n"
            f"{signature}"
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
