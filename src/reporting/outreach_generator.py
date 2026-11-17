"""Outreach Draft Generator for high-quality verified prospects.
Strictly produces draft templates with default status 'Pending Approval'.
NEVER dispatches or sends emails automatically.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from ..utils.url_utils import generate_stable_id, extract_domain


class OutreachDraftGenerator:
    """Generates thoughtful, individually tailored editorial outreach drafts."""

    def generate_draft(
        self,
        publication: str,
        target_url: str,
        angle: str,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_source: Optional[str] = None,
        evidence: str = ""
    ) -> Dict[str, Any]:
        """Generate a personalized draft strictly marked 'Pending Approval'."""
        clean_name = contact_name if contact_name else "Editorial Team"
        domain = extract_domain(target_url) or publication
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if angle == "Unlinked Brand Mention":
            subject = f"Quick question regarding your mention of IA Spaces on {domain}"
            body = (
                f"Hi {clean_name},\n\n"
                f"I came across your insightful coverage on {domain} here:\n{target_url}\n\n"
                f"Thank you for referencing IA Spaces in your piece. I noticed our name is mentioned without an active link to our primary resource hub.\n\n"
                f"Would you be open to adding a reference hyperlink to https://iaspaces.co so your readers can easily explore our flexible workspaces and ecosystem details?\n\n"
                f"Either way, thank you for the thoughtful coverage!\n\n"
                f"Warm regards,\n"
                f"IA Spaces Communications Team\n"
                f"https://iaspaces.co"
            )
        elif angle == "Listicle Inclusion":
            subject = f"Resource contribution for your {domain} coworking roundup"
            body = (
                f"Hi {clean_name},\n\n"
                f"I enjoyed reading your recent curated guide on flexible workspace solutions in India on {domain}:\n{target_url}\n\n"
                f"Given your focus on high-growth regional hubs, I wanted to suggest including IA Spaces (the coworking arm of India Accelerator). We operate 15+ managed hubs across Delhi NCR, Gurugram, Pune, Noida, Ahmedabad, and Tier-2 markets like Indore.\n\n"
                f"Here is our portal for quick review: https://iaspaces.co\n\n"
                f"Would this be a valuable addition to your readers in your next guide refresh?\n\n"
                f"Best regards,\n"
                f"IA Spaces Partnerships\n"
                f"https://iaspaces.co"
            )
        elif angle == "Tier-2 Expansion / Commentary":
            subject = f"Editorial insight / Commentary on Tier-2 workspace decentralization"
            body = (
                f"Hi {clean_name},\n\n"
                f"Following your coverage of commercial real estate trends on {domain} ({target_url}), I wanted to share a unique angle.\n\n"
                f"IA Spaces, backed by India Accelerator, has seen over 40% YoY uptake in managed enterprise seats across Tier-2 hubs like Indore and Ahmedabad as tech enterprises decentralize from metro centers.\n\n"
                f"If you are working on upcoming stories around workspace trends or Tier-2 startup ecosystems, our leadership team (including Ashish Bhatia, Co-Founder) would be delighted to share granular market data or commentary.\n\n"
                f"More background: https://iaspaces.co\n\n"
                f"Warm regards,\n"
                f"IA Spaces Editorial Team"
            )
        else:
            subject = f"Editorial inquiry regarding {domain} and IA Spaces"
            body = (
                f"Hi {clean_name},\n\n"
                f"Hope this finds you well. Reaching out from IA Spaces regarding your article on {domain}:\n{target_url}\n\n"
                f"We would love to share supporting context and data on flexible workspaces in India (https://iaspaces.co) if relevant for your upcoming features.\n\n"
                f"Best regards,\n"
                f"IA Spaces Team"
            )

        draft_id = generate_stable_id(f"{target_url}::{subject}", prefix="OUT")

        return {
            "id": draft_id,
            "publication": publication or domain,
            "contact_name": contact_name or "Unverified / Editorial Desk",
            "contact_email": contact_email or "Unverified (Requires Manual Lookup)",
            "contact_source": contact_source or "Public Website / Byline",
            "target_url": target_url,
            "proposed_subject": subject,
            "draft_email": body,
            "approval_status": "Pending Approval",
            "created_date": now_str
        }
