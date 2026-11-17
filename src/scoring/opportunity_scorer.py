"""Transparent Opportunity Scoring Engine (0-100 scale).
Evaluates prospects purely on verified topical relevance, geographic focus,
editorial authenticity, and outreach viability without fabricated metrics.
"""

from typing import Dict, Any, List

RELEVANT_CRE_KEYWORDS = [
    "coworking", "managed office", "flexible workspace", "commercial real estate",
    "office space", "incubation", "accelerator", "proptech", "startup ecosystem",
    "workplace", "hybrid work", "cre"
]

INDIA_KEYWORDS = [
    "india", "delhi", "gurugram", "gurgaon", "noida", "bengaluru", "bangalore",
    "mumbai", "pune", "hyderabad", "ahmedabad", "indore", "jaipur", "lucknow", "tier-2"
]

EDITORIAL_INDICATORS = [
    "article", "story", "news", "insights", "blog", "roundup", "opinion",
    "interview", "feature", "analysis", "report"
]


class OpportunityScorer:
    """Scores outreach and backlink prospects with full transparency."""

    def score_prospect(
        self,
        url: str,
        title: str = "",
        content_snippet: str = "",
        domain: str = "",
        has_contact_info: bool = False,
        is_editorial: bool = True,
        is_competitor_coverage: bool = False
    ) -> Dict[str, Any]:
        """Calculate transparent 0-100 score based on 6 documented pillars."""
        text = f"{title} {content_snippet} {url}".lower()

        # 1. Relevance to Coworking / CRE (0-25 pts)
        cre_matches = [k for k in RELEVANT_CRE_KEYWORDS if k in text]
        if len(cre_matches) >= 3:
            cre_score = 25
        elif len(cre_matches) == 2:
            cre_score = 18
        elif len(cre_matches) == 1:
            cre_score = 10
        else:
            cre_score = 0

        # 2. Relevance to India (0-20 pts)
        india_matches = [k for k in INDIA_KEYWORDS if k in text] or (".in" in domain or "indiatimes" in domain or "inc42" in domain or "yourstory" in domain)
        if isinstance(india_matches, list):
            if len(india_matches) >= 2:
                india_score = 20
            elif len(india_matches) == 1:
                india_score = 12
            else:
                india_score = 0
        else:
            india_score = 20 if india_matches else 0

        # 3. Evidence of Genuine Editorial Content (0-20 pts)
        # Avoid link farms, scrape directories, or coupon aggregators
        non_editorial_signals = ["coupon", "discount", "gambling", "casino", "free-backlink", "directory-submission"]
        if any(bad in text for bad in non_editorial_signals):
            editorial_score = 0
        elif is_editorial:
            editorial_matches = [e for e in EDITORIAL_INDICATORS if e in text]
            editorial_score = 20 if len(editorial_matches) >= 1 else 14
        else:
            editorial_score = 8

        # 4. Existing Relevant Coverage / Listicle Gap (0-15 pts)
        if is_competitor_coverage:
            coverage_score = 15
        elif any(k in text for k in ["list", "best", "top", "roundup", "options"]):
            coverage_score = 12
        else:
            coverage_score = 7

        # 5. Likelihood of Legitimate Contribution (0-10 pts)
        # Publications covering founder stories, guest contributions, or PR quotes
        guest_op_signals = ["contributor", "guest post", "opinion", "editorial", "contact editor", "write for us", "insights"]
        if any(sig in text for sig in guest_op_signals):
            contrib_score = 10
        elif is_editorial:
            contrib_score = 7
        else:
            contrib_score = 3

        # 6. Contact Information Verification (0-10 pts)
        contact_score = 10 if has_contact_info else 0

        total_score = min(100, cre_score + india_score + editorial_score + coverage_score + contrib_score + contact_score)

        # Determine priority tier
        if total_score >= 75:
            priority = "High"
        elif total_score >= 50:
            priority = "Medium"
        else:
            priority = "Low"

        breakdown = (
            f"CRE: {cre_score}/25, India: {india_score}/20, Editorial: {editorial_score}/20, "
            f"Coverage: {coverage_score}/15, Viability: {contrib_score}/10, Contact: {contact_score}/10"
        )

        return {
            "total_score": total_score,
            "priority": priority,
            "breakdown": breakdown,
            "cre_score": cre_score,
            "india_score": india_score,
            "editorial_score": editorial_score,
            "coverage_score": coverage_score,
            "viability_score": contrib_score,
            "contact_score": contact_score
        }
