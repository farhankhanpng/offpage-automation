"""Generates search query operators for manual verification and discovery.
Zero scraping of Google search results — produces copy-pasteable and clickable queries.
"""

from typing import List, Dict
import urllib.parse


def generate_manual_search_queries() -> List[Dict[str, str]]:
    """Generate curated search queries for safe manual prospecting."""
    queries = [
        {
            "category": "Brand Mentions (Unlinked)",
            "query": '"IA Spaces" -site:iaspaces.co',
            "purpose": "Find unlinked editorial mentions of IA Spaces",
        },
        {
            "category": "Parent Brand Mentions",
            "query": '"India Accelerator" ("coworking" OR "spaces" OR "managed office") -site:indiaaccelerator.co -site:iaspaces.co',
            "purpose": "Find ecosystem mentions ripe for IA Spaces co-attribution",
        },
        {
            "category": "Sub-Brand Mentions",
            "query": '"MySOHO" ("coworking" OR "accelerator" OR "office") -site:iaspaces.co',
            "purpose": "Find mentions of IA Spaces residential/coworking brand MySOHO",
        },
        {
            "category": "Competitor Editorial Coverage",
            "query": 'site:inc42.com ("Awfis" OR "Smartworks" OR "Innov8") "coworking"',
            "purpose": "Find recent Inc42 coworking roundups for editorial outreach",
        },
        {
            "category": "Competitor Editorial Coverage",
            "query": 'site:yourstory.com ("IndiQube" OR "Awfis" OR "WeWork India") "flexible workspace"',
            "purpose": "Find YourStory ecosystem stories covering flexible workspaces",
        },
        {
            "category": "Regional Commercial Real Estate",
            "query": 'site:economictimes.indiatimes.com "coworking" ("Gurugram" OR "Noida" OR "Pune")',
            "purpose": "Track Tier-1 & Tier-2 regional expansion stories",
        },
        {
            "category": "Startup Ecosystem Listicles",
            "query": 'intitle:"top coworking" ("Delhi NCR" OR "Gurugram" OR "Bengaluru")',
            "purpose": "Identify curated listicles where IA Spaces can be included",
        },
        {
            "category": "Tier-2 Startup Hubs",
            "query": '("coworking" OR "incubation center") ("Indore" OR "Ahmedabad" OR "Jaipur")',
            "purpose": "Find Tier-2 state ecosystem roundups for IA Spaces regional hubs",
        }
    ]

    for q in queries:
        encoded = urllib.parse.quote_plus(q["query"])
        q["google_search_url"] = f"https://www.google.com/search?q={encoded}"
        q["bing_search_url"] = f"https://www.bing.com/search?q={encoded}"

    return queries
