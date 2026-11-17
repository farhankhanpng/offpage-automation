"""URL utilities for normalisation, sanitisation, and stable ID generation.
"""

import re
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'fbclid', 'msclkid', 'mc_cid', 'mc_eid', 'ref', 'source'
}


def normalize_url(url: str) -> str:
    """Normalize a URL by stripping tracking parameters, normalizing scheme/host,

    and removing redundant fragments and trailing slashes (except root).
    """
    if not url or not isinstance(url, str):
        return ''

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
    except Exception:
        return url

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip default ports
    if (scheme == 'http' and netloc.endswith(':80')) or (scheme == 'https' and netloc.endswith(':443')):
        netloc = netloc.rsplit(':', 1)[0]

    # Normalize path
    path = parsed.path or '/'
    # Remove redundant slashes
    path = re.sub(r'/+', '/', path)
    if len(path) > 1 and path.endswith('/'):
        path = path[:-1]

    # Strip tracking parameters and sort remaining query params
    filtered_query = []
    if parsed.query:
        pairs = parse_qsl(parsed.query, keep_blank_values=False)
        filtered_query = sorted([(k, v) for k, v in pairs if k.lower() not in TRACKING_PARAMS])

    query = urlencode(filtered_query) if filtered_query else ''

    # Reconstruct without fragment
    normalized = urlunparse((scheme, netloc, path, '', query, ''))
    return normalized


def extract_domain(url: str) -> str:
    """Extract registered/clean domain or hostname from URL."""
    if not url:
        return ''
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        if ':' in domain:
            domain = domain.split(':', 1)[0]
        return domain
    except Exception:
        return ''


def generate_stable_id(url_or_key: str, prefix: str = 'ID') -> str:
    """Generate a deterministic 12-character alphanumeric ID based on SHA256 of normalized input."""
    clean = normalize_url(url_or_key) if url_or_key.startswith(('http://', 'https://', 'www.')) else url_or_key.strip().lower()
    hash_digest = hashlib.sha256(clean.encode('utf-8')).hexdigest()
    return f"{prefix}-{hash_digest[:10].upper()}"


def is_valid_url(url: str) -> bool:
    """Check if string is a syntactically valid public http/https URL."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc) and '.' in parsed.netloc
    except Exception:
        return False
