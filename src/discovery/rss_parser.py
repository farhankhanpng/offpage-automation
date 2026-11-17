"""Public RSS and Google Alerts RSS parser with feedparser & ElementTree fallback.
"""

import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger
from ..utils.url_utils import normalize_url, extract_domain

logger = get_logger("RSSParser")


class RSSFeedParser:
    """Parses standard RSS 2.0, Atom feeds, and Google Alerts RSS feeds."""

    def __init__(self, user_agent: str = "IASpaces-OffPage-Bot/1.0", timeout: int = 15):
        self.user_agent = user_agent
        self.timeout = timeout

    def fetch_feed_xml(self, feed_url: str) -> Optional[str]:
        """Fetch raw XML content with timeout and custom User-Agent."""
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": self.user_agent, "Accept": "application/rss+xml, application/atom+xml, text/xml"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Failed to fetch RSS feed {feed_url}: {e}")
            return None

    def parse_feed_string(self, xml_text: str, source_label: str = "RSS") -> List[Dict[str, Any]]:
        """Parse XML string into standardized article records."""
        items: List[Dict[str, Any]] = []
        if not xml_text:
            return items

        # Attempt feedparser if installed
        try:
            import feedparser
            feed = feedparser.parse(xml_text)
            for entry in feed.entries:
                link = getattr(entry, "link", "").strip()
                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                pub_date = getattr(entry, "published", "") or getattr(entry, "updated", "")
                norm_url = normalize_url(link)
                if norm_url:
                    items.append({
                        "url": norm_url,
                        "raw_url": link,
                        "title": title,
                        "summary": summary,
                        "published_date": pub_date,
                        "domain": extract_domain(norm_url),
                        "source": source_label,
                        "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            if items:
                return items
        except ImportError:
            pass

        # Standard library ElementTree fallback
        try:
            root = ET.fromstring(xml_text)
            # Check RSS 2.0 /channel/item
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                pub_elem = item.find("pubDate")

                link = (link_elem.text if link_elem is not None and link_elem.text else "").strip()
                title = (title_elem.text if title_elem is not None and title_elem.text else "").strip()
                summary = (desc_elem.text if desc_elem is not None and desc_elem.text else "").strip()
                pub_date = (pub_elem.text if pub_elem is not None and pub_elem.text else "").strip()

                norm_url = normalize_url(link)
                if norm_url:
                    items.append({
                        "url": norm_url,
                        "raw_url": link,
                        "title": title,
                        "summary": summary,
                        "published_date": pub_date,
                        "domain": extract_domain(norm_url),
                        "source": source_label,
                        "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })

            # Check Atom <entry>
            # Namespaces often used in Atom
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns) or root.findall(".//entry"):
                title_elem = entry.find("atom:title", ns) if "atom:" in entry.tag else entry.find("title")
                link_elem = entry.find("atom:link", ns) if "atom:" in entry.tag else entry.find("link")
                summary_elem = entry.find("atom:content", ns) or entry.find("atom:summary", ns) or entry.find("summary")
                pub_elem = entry.find("atom:published", ns) or entry.find("atom:updated", ns) or entry.find("updated")

                link = ""
                if link_elem is not None:
                    link = link_elem.attrib.get("href", link_elem.text or "").strip()

                title = (title_elem.text if title_elem is not None and title_elem.text else "").strip()
                summary = (summary_elem.text if summary_elem is not None and summary_elem.text else "").strip()
                pub_date = (pub_elem.text if pub_elem is not None and pub_elem.text else "").strip()

                norm_url = normalize_url(link)
                if norm_url:
                    items.append({
                        "url": norm_url,
                        "raw_url": link,
                        "title": title,
                        "summary": summary,
                        "published_date": pub_date,
                        "domain": extract_domain(norm_url),
                        "source": source_label,
                        "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
        except Exception as e:
            logger.warning(f"Error parsing XML feed with ElementTree: {e}")

        return items

    def fetch_and_parse(self, feed_url: str, source_label: str = "RSS") -> List[Dict[str, Any]]:
        xml_text = self.fetch_feed_xml(feed_url)
        if not xml_text:
            return []
        return self.parse_feed_string(xml_text, source_label=source_label)
