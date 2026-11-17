"""Unit tests for transparent opportunity scoring.
"""

import unittest
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.scoring.opportunity_scorer import OpportunityScorer


class TestOpportunityScorer(unittest.TestCase):

    def setUp(self):
        self.scorer = OpportunityScorer()

    def test_high_priority_coworking_lead(self):
        result = self.scorer.score_prospect(
            url="https://inc42.com/features/top-coworking-spaces-in-delhi-ncr-2026/",
            title="Top Coworking Spaces in Delhi NCR and Gurugram",
            content_snippet="Comparing managed office options, commercial real estate trends and best flexible workspace providers.",
            domain="inc42.com",
            has_contact_info=True,
            is_editorial=True,
            is_competitor_coverage=True
        )
        self.assertGreaterEqual(result["total_score"], 75)
        self.assertEqual(result["priority"], "High")
        self.assertEqual(result["cre_score"], 25)
        self.assertEqual(result["india_score"], 20)
        self.assertEqual(result["coverage_score"], 15)
        self.assertEqual(result["contact_score"], 10)

    def test_low_priority_irrelevant_prospect(self):
        result = self.scorer.score_prospect(
            url="https://generic-travel.com/hotels-in-paris",
            title="Best Budget Hotels in Paris",
            content_snippet="Affordable accommodation options in France.",
            domain="generic-travel.com",
            has_contact_info=False,
            is_editorial=False
        )
        self.assertLess(result["total_score"], 40)
        self.assertEqual(result["priority"], "Low")
        self.assertEqual(result["cre_score"], 0)
        self.assertEqual(result["india_score"], 0)

    def test_no_fabricated_metrics_present(self):
        result = self.scorer.score_prospect(
            url="https://example.com/story",
            title="Sample Story",
            content_snippet="Test",
            domain="example.com"
        )
        self.assertNotIn("domain_authority", result)
        self.assertNotIn("domain_rating", result)
        self.assertNotIn("estimated_traffic", result)


if __name__ == "__main__":
    unittest.main()
