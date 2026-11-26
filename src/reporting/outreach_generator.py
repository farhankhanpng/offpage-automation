"""Outreach Draft Generator.

Produces draft emails with status "Pending Approval". It NEVER sends anything.

Rules:
  - drafts are only created for pages that were fetched and inspected (enforced by the runner);
  - drafts follow the reference email approved by the Marketing Manager (2026-11-25):
    greeting, the article (title and link), who IA Spaces is, the India Accelerator ecosystem,
    every IA Spaces hub in the city the article is about (and no other city), the request,
    and the signature;
  - hub/city counts come from settings.yaml -> brand_facts, which records where they were checked;
  - hub names, areas and hub-page links come from the master hub file
    (data/ia-spaces-nap-master.csv), the same file the citation check uses; every hub link
    there is listed in iaspaces.co/sitemap.xml;
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
}

DEFAULT_SENDER = {"name": "", "title": "Marketing Manager", "email": "", "phone": ""}

ANGLES = ["Unlinked Brand Mention", "Listicle Inclusion", "Tier-2 Expansion / Commentary", "Industry Commentary"]

# Spellings used in articles -> the city name used in the hub file
CITY_ALIASES = {
    "gurgaon": "Gurugram", "bombay": "Mumbai", "navi mumbai": "Mumbai", "vizag": "Visakhapatnam",
    "bangalore": "Bengaluru", "delhi": "New Delhi", "calcutta": "Kolkata", "sas nagar": "Mohali",
}

NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
                8: "eight", 9: "nine", 10: "ten"}

# Address phrases shown the way people say them
AREA_NORMALISE = [
    (r"^Mehrauli-Gurgaon \(MG\) Road$", "MG Road"),
    (r"^Mehrauli-Gurgaon Road$", "MG Road"),
    (r"^(near|opp\.?|opposite)\s+", ""),
]


# Site names that pages append to their titles
TITLE_SUFFIX_RE = re.compile(
    r"\s*[|\u2013\u2014-]\s*(Outlook Business|Business|YourStory|Devdiscourse|ThisWeekInCoworking\.com|"
    r"Daily Excelsior|The Economic Times|ET RealEstate|Mint|Livemint|Office Khojo|An Honest Comparison)\s*$",
    re.IGNORECASE)
# Pages whose <title> is only the site's own name: the real headline is not in the title
GENERIC_TITLES = {"discuss twic stories, links and trends."}
KNOWN_HEADLINES = {"thisweekincoworking.com/discuss/item/mxxew": "IA acquires MySOHO"}


def clean_title(title: str, url: str = "") -> str:
    """Headline without the site name ('X - Outlook Business' -> 'X')."""
    t = (title or "").strip()
    for _ in range(3):
        new = TITLE_SUFFIX_RE.sub("", t).strip()
        if new == t:
            break
        t = new
    return t


def _hub_short_name(business_name: str) -> str:
    """'IA Spaces - MG Road, Gurugram' -> 'MG Road'."""
    name = re.sub(r"^\s*IA Spaces\s*-\s*", "", business_name or "")
    return name.rsplit(",", 1)[0].strip()


def _hub_area(hub: Dict[str, str]) -> str:
    """The first readable part of Address Line 2, e.g. 'Golf Course Extension Road'."""
    for part in (hub.get("Address Line 2") or "").split(","):
        part = part.strip()
        for pattern, repl in AREA_NORMALISE:
            part = re.sub(pattern, repl, part, flags=re.IGNORECASE).strip()
        if not part or not re.search(r"[A-Za-z]{3}", part) or re.match(r"^\d", part):
            continue
        if part.lower() in ("station",):
            continue
        return part
    return ""


def hub_label(hub: Dict[str, str]) -> str:
    """'Imperia, Golf Course Extension Road'; just 'MG Road' when the area repeats the name."""
    name = _hub_short_name(hub.get("Business Name", ""))
    area = _hub_area(hub)
    if not area or area.lower() in name.lower() or name.lower() in area.lower():
        return name
    return f"{name}, {area}"


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
        known = []
        for h in self.hubs:
            if h["City"] not in known:
                known.append(h["City"])
        candidates = [(c.lower(), c) for c in known]
        candidates += [(k, v) for k, v in CITY_ALIASES.items() if v in known]
        hits = set()
        for word, city in candidates:
            if re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", t):
                hits.add(city)
        return [c for c in known if c in hits]

    def _hubs_in(self, city: str) -> List[Dict[str, str]]:
        return [h for h in self.hubs if h["City"] == city]

    def _city_block(self, cities: List[str]) -> str:
        """Every hub in the city (or cities) the article is about; nothing for other cities."""
        parts = []
        with_hubs = [c for c in cities if self._hubs_in(c)]
        for city in with_hubs:
            hubs = self._hubs_in(city)
            n = len(hubs)
            if n == 1:
                lead = f"In {city}, IA Spaces operates a hub at a prominent business location:"
            else:
                where = f"In {city} alone" if len(with_hubs) == 1 else f"In {city}"
                lead = f"{where}, IA Spaces operates {NUMBER_WORDS.get(n, str(n))} hubs across prominent business locations:"
            lines = "\n".join(f"- {hub_label(h)}: {h.get('Website', '').strip()}" for h in hubs)
            parts.append(f"{lead}\n\n{lines}")
        return ("\n\n".join(parts) + "\n\n") if parts else ""

    def _signature(self) -> str:
        f, s = self.facts, self.sender
        lines = ["Warm regards,", "", s["name"] or "XXX", f"{s['title'] or 'Marketing Manager'} | IA Spaces", ""]
        if s.get("phone"):
            lines.append(f"Mobile: {s['phone']}")
        if s.get("email"):
            lines.append(f"Email: {s['email']}")
        lines.append(f"Website: {f['website']}")
        return "\n".join(lines)

    @staticmethod
    def _greeting(contact_name: Optional[str]) -> str:
        name = (contact_name or "").strip()
        if not name or "not verified" in name.lower() or name.lower() == "editorial team":
            return "Dear Editor,"
        return f"Dear {name},"

    def _about(self) -> str:
        f = self.facts
        return (
            f"IA Spaces is the coworking and managed-office network of {f['parent']}, an established "
            f"name in India's startup, accelerator and investment ecosystem. With {f['hubs']} hubs "
            f"across {f['cities']} cities, IA Spaces brings together premium workspace infrastructure "
            f"and access to a larger startup ecosystem.\n\n"
            f"Unlike conventional coworking spaces, its association with {f['parent']} gives founders "
            f"opportunities to engage with experienced mentors, participate in mentor sessions and demo "
            f"days, connect with investors, explore potential funding opportunities and access "
            f"accelerator programmes, subject to eligibility."
        )

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
        title = clean_title(page_title)
        if title.lower() in GENERIC_TITLES or not title:
            key = re.sub(r"^https?://(www\.)?", "", target_url).rstrip("/")
            title = KNOWN_HEADLINES.get(key, title)
        article = f'"{title}"' if title else "on your website"
        quoted = f'"{title}"' if title else "your recent article"
        cities = self._cities_in(f"{title} {evidence}")
        greeting = self._greeting(contact_name)
        offer = "I would be happy to share a brief brand profile, photographs and any additional information you may need."

        if angle == "Unlinked Brand Mention":
            target = f["website"]
            city_hubs = [h for c in cities for h in self._hubs_in(c)]
            if len(city_hubs) == 1:
                target = city_hubs[0].get("Website", "").strip() or target
            named = "IA Spaces" if brand.strip().lower() in ("ia spaces", "iaspaces.co") else brand
            subject = f"Thank you for mentioning {named} in {quoted}"
            opening = (f"I recently came across your article, {article}, and wanted to thank you for "
                       f"mentioning {named}.")
            ask = (f"We would appreciate it if you could consider mentioning IA Spaces by name in your "
                   f"article and linking it to this page:\n{target}\n\n{offer}")
        elif angle == "Listicle Inclusion":
            subject = f"Request to feature IA Spaces in {quoted}"
            opening = (f"I recently came across your article, {article}, and wanted to introduce "
                       f"IA Spaces for your consideration.")
            ask = f"We would appreciate it if you could consider including IA Spaces in your article. {offer}"
        else:  # Industry Commentary and Tier-2 Expansion / Commentary
            subject = f"Request to feature IA Spaces in {quoted}"
            opening = (f"I recently came across your article, {article}, and wanted to introduce "
                       f"IA Spaces for your consideration in your coverage of coworking and flexible workspaces.")
            ask = (f"We would appreciate it if you could consider including IA Spaces in your article or "
                   f"in your future coverage. {offer}")

        body = (
            f"{greeting}\n\n"
            f"I hope you are doing well.\n\n"
            f"{opening}\n\n"
            f"Article link: {target_url}\n\n"
            f"{self._about()}\n\n"
            f"{self._city_block(cities)}"
            f"{ask}\n\n"
            f"Thank you for your time and consideration. Looking forward to hearing from you.\n\n"
            f"{self._signature()}"
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

    # ---------- refreshing drafts already in the Sheet ----------

    def refresh_existing(self, row: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Rewrite an Outreach row that this run did not rediscover, so every draft in the Sheet
        uses the current template. Returns the new Subject/Draft Email, or None if the row's
        angle cannot be worked out from its ID. Human columns are never touched."""
        # Drafts the team has approved, sent or rejected are left exactly as they are,
        # so edits made in the Sheet are never overwritten.
        if (row.get("Approval Status") or "Pending Approval").strip() != "Pending Approval":
            return None
        url = (row.get("Target URL") or "").strip()
        rid = (row.get("ID") or "").strip()
        if not url or not rid:
            return None
        angle = next((a for a in ANGLES if generate_stable_id(f"{url}::{a}", prefix="OUT") == rid), None)
        if not angle:
            return None
        old = row.get("Draft Email") or ""
        title = ""
        m = re.search(r'came across (?:your article, )?"(.+?)"(?: \(|,| on |\n|$)', old)
        if not m:
            m = re.search(r'"(.+?)"', old)
        if m:
            title = m.group(1).strip()
        brand = "IA Spaces"
        b = re.search(r"mentioning (India Accelerator|MySOHO|IA Spaces)", old)
        if b:
            brand = b.group(1)
        contact = row.get("Contact Name") or ""
        d = self.generate_draft(publication=row.get("Publication", ""), target_url=url, angle=angle,
                                contact_name=contact, page_title=title, brand=brand)
        return {"Proposed Subject": d["proposed_subject"], "Draft Email": d["draft_email"]}


def pick_contact(emails: List[str]) -> Optional[str]:
    """Prefer editorial-looking addresses published on the page."""
    preferred = ("editor", "editorial", "news", "tips", "contribut", "content", "press", "features")
    for e in emails:
        if any(p in e.split("@")[0] for p in preferred):
            return e
    return emails[0] if emails else None
