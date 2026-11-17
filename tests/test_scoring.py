"""Unit tests for transparent opportunity scoring."""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.scoring.opportunity_scorer import OpportunityScorer  # noqa: E402


class TestOpportunityScorer(unittest.TestCase):

    def setUp(self):
        self.scorer = OpportunityScorer()

    def test_high_priority_coworking_lead(self):
        result = self.scorer.score_prospect(
            url="https://inc42.com/features/top-coworking-spaces-in-delhi-ncr/",
            title="Top Coworking Spaces in Delhi NCR and Gurugram",
            content_snippet="Comparing managed office options, commercial real estate trends and the best flexible workspace providers.",
            domain="inc42.com",
            has_contact_info=True,
            is_editorial=True,
            is_competitor_coverage=True,
        )
        self.assertGreaterEqual(result["total_score"], 75)
        self.assertEqual(result["priority"], "High")
        self.assertEqual(result["cre_score"], 30)
        self.assertEqual(result["coverage_score"], 20)
        self.assertEqual(result["contact_score"], 10)
        self.assertTrue(self.scorer.qualifies_for_outreach(result, 65))

    def test_low_priority_irrelevant_prospect(self):
        result = self.scorer.score_prospect(
            url="https://generic-travel.com/hotels-in-paris",
            title="Best Budget Hotels in Paris",
            content_snippet="Affordable accommodation options in France.",
            domain="generic-travel.com",
        )
        self.assertLessEqual(result["total_score"], 25)
        self.assertEqual(result["priority"], "Not Relevant")
        self.assertEqual(result["cre_score"], 0)
        self.assertEqual(result["india_score"], 0)

    def test_unrelated_indian_startup_story_does_not_qualify(self):
        # Previously scored 68 because "cre" matched "create"/"credit" and contact/editorial were hard-coded True.
        result = self.scorer.score_prospect(
            url="https://inc42.com/buzz/fintech-startup-raises-funding/",
            title="Fintech startup raises $5 Mn to create credit platform for Indian SMEs",
            content_snippet="The company will use the funds to increase its credit underwriting team.",
            domain="inc42.com",
            is_editorial=True,
        )
        self.assertEqual(result["cre_score"], 0)
        self.assertEqual(result["priority"], "Not Relevant")
        self.assertFalse(self.scorer.qualifies_for_outreach(result, 65))

    def test_unfetched_page_is_capped_and_unverified(self):
        result = self.scorer.score_prospect(
            url="https://inc42.com/features/top-coworking-spaces/",
            title="Top coworking spaces in Gurugram: managed office and flexible workspace guide",
            domain="inc42.com",
            has_contact_info=True,
            is_competitor_coverage=True,
            page_fetched=False,
        )
        self.assertLessEqual(result["total_score"], 49)
        self.assertEqual(result["priority"], "Unverified")
        self.assertFalse(self.scorer.qualifies_for_outreach(result, 0))

    def test_spam_is_rejected(self):
        result = self.scorer.score_prospect(
            url="https://spam.example/coworking-coupon-codes",
            title="Coworking coupon codes India", domain="spam.example")
        self.assertEqual(result["total_score"], 0)
        self.assertEqual(result["priority"], "Rejected")

    def test_no_fabricated_metrics_present(self):
        result = self.scorer.score_prospect(url="https://example.com/story", title="Sample Story")
        for key in ("domain_authority", "domain_rating", "estimated_traffic"):
            self.assertNotIn(key, result)


if __name__ == "__main__":
    unittest.main()
