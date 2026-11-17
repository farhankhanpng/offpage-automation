"""Transparent Opportunity Scoring Engine (0-100).

Six documented pillars, all matched as whole words on the page's title and opening text:
  1. Coworking / CRE relevance ........ 0-30
  2. India relevance .................. 0-15
  3. Editorial content ................ 0-15
  4. Coverage gap (competitor/listicle) 0-20
  5. Contribution route ............... 0-10
  6. Contact found on the page ........ 0-10

Gates (so unrelated or unread pages can never qualify for outreach):
  - no coworking/CRE term at all      -> total capped at 25, priority "Not Relevant";
  - the page was not actually fetched -> total capped at 49, priority "Unverified";
  - spam signals (coupon, casino, ...) -> total 0, priority "Rejected".
No third-party authority metrics (DA/DR/traffic) are estimated.
"""

from typing import Any, Dict
from urllib.parse import urlparse

from ..utils.text_match import matching_phrases

RELEVANT_CRE_KEYWORDS = [
    "coworking", "co-working", "coworking space", "managed office", "managed offices",
    "flexible workspace", "flexible workspaces", "flex space", "flexible office",
    "shared office", "office space", "office spaces", "commercial real estate",
    "office leasing", "workspace", "workspaces", "incubation", "incubator",
    "accelerator", "proptech", "hybrid work", "startup ecosystem",
]

INDIA_KEYWORDS = [
    "india", "indian", "delhi", "ncr", "gurugram", "gurgaon", "noida", "bengaluru",
    "bangalore", "mumbai", "pune", "hyderabad", "chennai", "ahmedabad", "indore",
    "jaipur", "lucknow", "chandigarh", "surat", "vadodara", "rajkot", "tier-2", "tier 2",
]

INDIAN_PUBLICATION_DOMAINS = [
    "inc42.com", "yourstory.com", "entrackr.com", "livemint.com", "indiatimes.com",
    "economictimes.com", "business-standard.com", "thehindubusinessline.com",
    "moneycontrol.com", "financialexpress.com", "businessworld.in", "realtynxt.com",
    "thepropertytimes.in", "outlookbusiness.com", "rprealtyplus.com",
]

EDITORIAL_WORDS = ["news", "story", "feature", "analysis", "report", "interview", "opinion", "insights", "guide"]
EDITORIAL_PATH_HINTS = ["/news", "/story", "/stories", "/features", "/feature", "/blog", "/article", "/insights", "/opinion"]
LISTICLE_WORDS = ["best", "top", "list", "roundup", "options", "alternatives", "comparison"]
CONTRIBUTION_WORDS = ["contributor", "guest post", "write for us", "submit", "opinion", "op-ed", "contact the editor"]
SPAM_SIGNALS = ["coupon", "promo code", "casino", "gambling", "betting", "free backlinks", "directory submission"]


class OpportunityScorer:
    def score_prospect(
        self,
        url: str,
        title: str = "",
        content_snippet: str = "",
        domain: str = "",
        has_contact_info: bool = False,
        is_editorial: bool = False,
        is_competitor_coverage: bool = False,
        page_fetched: bool = True,
    ) -> Dict[str, Any]:
        text = f"{title} {content_snippet[:4000]}"
        path = urlparse(url).path.lower() if url else ""
        domain = (domain or urlparse(url).netloc or "").lower()

        # Spam gate
        if matching_phrases(f"{text} {path.replace('-', ' ')}", SPAM_SIGNALS):
            return self._result(0, "Rejected", 0, 0, 0, 0, 0, 0, note="spam signals")

        # 1. CRE relevance (0-30)
        cre = matching_phrases(text, RELEVANT_CRE_KEYWORDS)
        cre_score = 0 if not cre else (10 if len(cre) == 1 else 20 if len(cre) == 2 else 30)

        # 2. India relevance (0-15)
        india = matching_phrases(text, INDIA_KEYWORDS)
        india_score = 0 if not india else (8 if len(india) == 1 else 15)
        if india_score < 15 and (domain.endswith(".in") or any(domain.endswith(d) for d in INDIAN_PUBLICATION_DOMAINS)):
            india_score = min(15, india_score + 5)

        # 3. Editorial content (0-15)
        editorial_hits = matching_phrases(text, EDITORIAL_WORDS) or [h for h in EDITORIAL_PATH_HINTS if h in path]
        editorial_score = 15 if (is_editorial and editorial_hits) else 10 if (is_editorial or editorial_hits) else 0

        # 4. Coverage gap (0-20)
        if is_competitor_coverage:
            coverage_score = 20
        elif matching_phrases(title, LISTICLE_WORDS):
            coverage_score = 12
        else:
            coverage_score = 0

        # 5. Contribution route (0-10)
        contrib_score = 10 if matching_phrases(text, CONTRIBUTION_WORDS) else 0

        # 6. Contact found on page (0-10)
        contact_score = 10 if has_contact_info else 0

        total = cre_score + india_score + editorial_score + coverage_score + contrib_score + contact_score
        if cre_score == 0:
            total, priority = min(total, 25), "Not Relevant"
        elif not page_fetched:
            total, priority = min(total, 49), "Unverified"
        else:
            priority = "High" if total >= 75 else "Medium" if total >= 50 else "Low"

        return self._result(total, priority, cre_score, india_score, editorial_score,
                            coverage_score, contrib_score, contact_score)

    @staticmethod
    def _result(total, priority, cre, india, editorial, coverage, contrib, contact, note: str = ""):
        breakdown = (
            f"CRE: {cre}/30, India: {india}/15, Editorial: {editorial}/15, "
            f"Coverage: {coverage}/20, Contribution: {contrib}/10, Contact: {contact}/10"
        )
        if note:
            breakdown += f" ({note})"
        return {
            "total_score": int(total),
            "priority": priority,
            "breakdown": breakdown,
            "cre_score": cre,
            "india_score": india,
            "editorial_score": editorial,
            "coverage_score": coverage,
            "viability_score": contrib,
            "contact_score": contact,
        }

    @staticmethod
    def qualifies_for_outreach(score: Dict[str, Any], threshold: int = 65) -> bool:
        return score.get("priority") in ("High", "Medium") and score.get("total_score", 0) >= threshold
