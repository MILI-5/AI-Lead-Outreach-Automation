
import re
import logging
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://hn.algolia.com/api/v1/search"

QUERIES = [
    "Show HN AI startup",
    "Show HN AI product",
    "Show HN SaaS",
    "launch AI startup",
]

BLOCKED_DOMAINS = {
    "github.com",
    "gitlab.com",
    "youtube.com",
    "youtu.be",
    "reddit.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "medium.com",
    "substack.com",
    "techcrunch.com",
    "nasdaq.com",
    "bloomberg.com",
    "forbes.com",
    "news.ycombinator.com",
    "ycombinator.com",
}

# Common hosting platforms are excluded because a project hosted
# on one of these domains is not necessarily an independent company.
HOSTING_DOMAINS = {
    "vercel.app",
    "netlify.app",
    "github.io",
    "pages.dev",
    "lovable.app",
    "webflow.io",
    "framer.website",
}

TITLE_PREFIXES = [
    r"^\s*show hn\s*:\s*",
    r"^\s*launch hn\s*:\s*",
]

TECH_TERMS = re.compile(
    r"\b(ai|artificial intelligence|llm|saas|startup|"
    r"product|platform|automation|software|machine learning|"
    r"developer tool|agent|generative ai)\b",
    re.IGNORECASE,
)


def normalize_domain(url: str) -> str | None:
    """Return a normalized hostname, or None for invalid URLs."""
    try:
        parsed = urlparse(url.strip())
        domain = (parsed.hostname or "").lower().removeprefix("www.")

        if parsed.scheme not in {"http", "https"}:
            return None

        if not domain or "." not in domain:
            return None

        if any(
            domain == blocked or domain.endswith("." + blocked)
            for blocked in BLOCKED_DOMAINS
        ):
            return None

        # Exclude common hosting subdomains from being treated
        # automatically as independent company websites.
        if any(
            domain == host or domain.endswith("." + host)
            for host in HOSTING_DOMAINS
        ):
            return None

        return domain

    except (ValueError, AttributeError):
        return None


def extract_company_name(title: str) -> str:
    """
    Remove common announcement prefixes and update suffixes.
    The result is a candidate name extracted from a public title,
    not a verified legal company name.
    """
    cleaned = title.strip()

    for prefix in TITLE_PREFIXES:
        cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE)

    # Remove common update suffixes such as "(Day 3 update)".
    cleaned = re.sub(
        r"\s*[\(\[]\s*(day\s+\d+|update|launch update)"
        r"[^)\]]*[\)\]]\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Keep the part before a descriptive dash where possible.
    # This is only a heuristic; product names can contain dashes.
    parts = re.split(r"\s+[–—]\s+", cleaned, maxsplit=1)
    if len(parts) > 1 and len(parts[0].strip()) >= 2:
        cleaned = parts[0].strip()

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:|")

    return cleaned[:255] or title[:255]


def discover_companies(limit: int = 10) -> list[dict]:
    """
    Discover public startup/product candidates using Hacker News Algolia.

    Returns candidate records with:
      name, company_name, company_website, industry, source, source_url

    These records are not verified contacts or guaranteed active companies.
    """
    if limit < 1:
        return []

    discovered = []
    seen_domains = set()
    session = requests.Session()

    for query in QUERIES:
        try:
            response = session.get(
                SEARCH_URL,
                params={
                    "query": query,
                    "tags": "story",
                    "hitsPerPage": 50,
                },
                timeout=15,
            )
            response.raise_for_status()
            hits = response.json().get("hits", [])

        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "Hacker News search failed for %r: %s",
                query,
                exc,
            )
            continue

        for hit in hits:
            title = (hit.get("title") or "").strip()
            story_url = (hit.get("url") or "").strip()
            object_id = hit.get("objectID")

            if not title or not story_url:
                continue

            if not TECH_TERMS.search(title):
                continue

            domain = normalize_domain(story_url)

            if not domain or domain in seen_domains:
                continue

            company_name = extract_company_name(title)

            if not company_name:
                continue

            seen_domains.add(domain)

            discovered.append({
                "name": "Contact not identified",
                "company_name": company_name,
                "company_website": f"https://{domain}",
                "industry": "AI / Technology",
                "source": "hacker_news",
                "source_url": (
                    f"https://news.ycombinator.com/item?id={object_id}"
                    if object_id
                    else story_url
                ),
                "verification_status": "Unverified",
            })

            if len(discovered) >= limit:
                session.close()
                return discovered

    session.close()
    return discovered
