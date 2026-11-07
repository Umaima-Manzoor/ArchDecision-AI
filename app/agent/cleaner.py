"""
Takes raw SearchResult objects from the Searcher and:
  1. Strips HTML artifacts and normalizes whitespace
  2. Filters out results that are too short to be useful
  3. Assigns a trust tier (0-4) based on the source domain
  4. Removes exact-URL duplicates
  5. Removes near-duplicate content using Jaccard similarity
  6. Sorts by trust tier and caps the result count

No API calls. No network. Pure Python
"""

import re
import logging
from urllib.parse import urlparse       # breaks url into components for domain extraction

from app.schemas import SearchResult

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 2000           # enough for LLM to extract context while staying in budget
MIN_CONTENT_LENGTH = 50
SIMILARITY_THRESHOLD = 0.6          # 60% similarity to be considered duplicates
MAX_RESULTS_AFTER_CLEANING = 15     # 25 to 15 - enough to find conflicts

# Tier 0 = Official documentation (highest trust)
TIER_0_DOMAINS: set[str] = { "postgresql.org", "mysql.com", "redis.io", "mongodb.com", "kafka.apache.org", "kubernetes.io", "docker.com", "nginx.org", "python.org", "golang.org", "nodejs.org", "rust-lang.org", "elastic.co", "cassandra.apache.org", "rabbitmq.com"}
TIER_0_PREFIXES: tuple[str, ...] = ("docs.", "developer.", "learn.")

# Tier 1 = Major cloud/tech vendor docs and engineering blogs
TIER_1_DOMAINS: set[str] = { "aws.amazon.com", "cloud.google.com","azure.microsoft.com", "learn.microsoft.com", "docs.aws.amazon.com", "engineering.fb.com", "netflixtechblog.com", "eng.uber.com", "grafana.com", "datadoghq.com","confluent.io", "hashicorp.com", "vercel.com", "supabase.com", "planetscale.com"}

# Tier 2 = Reputable community sources (Stack Overflow, GitHub, etc.)
TIER_2_DOMAINS: set[str] = {"stackoverflow.com","stackexchange.com", "github.com", "gitlab.com", "arxiv.org", "infoq.com", "thenewstack.io", "db-engines.com", "thoughtworks.com", "martinfowler.com"}

# Tier 3 = General blogs and forums (default for unknown domains)
TIER_3_DOMAINS: set[str] = {"medium.com", "dev.to", "hashnode.dev","substack.com"}

# Tier 4 = Known low-quality / SEO-heavy sites
TIER_4_DOMAINS: set[str] = {"tutorialspoint.com", "geeksforgeeks.org", "javatpoint.com", "w3schools.com" }


_HTML_TAG_RE = re.compile(r"<[^>]+>")       # Matches any HTML tag: <div>, </p>, <a href="...">, etc.
_WHITESPACE_RE = re.compile(r"\s+")     # Matches runs of whitespace (spaces, tabs, newlines)

# Common boilerplate phrases to strip
_BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"cookie\s+(consent|policy|settings)", re.IGNORECASE),
    re.compile(r"(subscribe|sign\s+up)\s+(to|for)\s+(our\s+)?(newsletter|updates)", re.IGNORECASE),
    re.compile(r"click\s+here\s+to\s+(read|learn|download|subscribe)", re.IGNORECASE),
    re.compile(r"(accept|reject)\s+(all\s+)?cookies", re.IGNORECASE),
    re.compile(r"share\s+(on|this)\s+(twitter|facebook|linkedin)", re.IGNORECASE),
]


def clean_text(text: str, max_length: int = MAX_CONTENT_LENGTH) -> str:     # Strip HTML tags, remove boilerplate, normalize whitespace, truncate.
    if not text:
        return ""

    cleaned = _HTML_TAG_RE.sub(" ", text)       # replace html tags with spaces

    for pattern in _BOILERPLATE_PATTERNS:       # remove common boilerplate phrases
        cleaned = pattern.sub("", cleaned)

    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()      # replace runs of whitespace with a single space and trim leading/trailing spaces

    if len(cleaned) > max_length:           # truncate to max_length, but try to cut at a word boundary
        truncated = cleaned[:max_length]
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.8:           # if the last space is in the last 20% of the truncated string, cut there
            truncated = truncated[:last_space]
        cleaned = truncated + "..."

    return cleaned

def assign_trust_tier(url: str) -> int:
    """Assign a trust tier (0-4) based on the URL's domain.
    Tier logic (checked in order):
      1. Exact domain match against TIER_0 / TIER_1 / TIER_2 / TIER_3 / TIER_4 sets
      2. Subdomain suffix match for TIER_0, TIER_1, TIER_3 (e.g. "docs.postgresql.org")
      3. Subdomain prefix match (docs.*, developer.*, learn.*) -> Tier 0
      4. Everything else -> Tier 3 (unknown but not penalized)
    """
    if not url:
        return 4

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""        # in case url was parsed but has no hostname (e.g., "file:///path/to/file")
    except Exception:
        return 4

    hostname = hostname.lower().removeprefix("www.")        # not replace because we only want to remove the first occurrence of "www." if it exists at the start

    # Check exact domain matches (order matters: check most specific first)
    if hostname in TIER_0_DOMAINS:
        return 0
    if hostname in TIER_1_DOMAINS:
        return 1
    if hostname in TIER_2_DOMAINS:
        return 2
    if hostname in TIER_3_DOMAINS:
        return 3
    if hostname in TIER_4_DOMAINS:
        return 4

    # Check if any TIER_0 domain is a suffix (handles subdomains like "docs.postgresql.org" or "dev.mysql.com")
    for domain in TIER_0_DOMAINS:
        if hostname.endswith("." + domain):
            return 0

    for domain in TIER_1_DOMAINS:
        if hostname.endswith("." + domain):
            return 1

    for domain in TIER_3_DOMAINS:
        if hostname.endswith("." + domain):
            return 3

    # Check subdomain prefixes for documentation sites
    for prefix in TIER_0_PREFIXES:
        if hostname.startswith(prefix):
            return 0

    # Default: unknown domain, moderate trust
    return 3

def _tokenize(text: str) -> set[str]:       # To reduce noise from articles and prepositions that inflate similarity scores.
    words = text.lower().split()
    return {w for w in words if len(w) > 2}     # set of words longer than 2 characters 

def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two texts
    Jaccard = |intersection| / |union| of word sets
    Returns 0.0 (completely different) to 1.0 (identical word sets)
    """
    set_a = _tokenize(text_a)
    set_b = _tokenize(text_b)

    if not set_a and not set_b:     # empty are considered identical
        return 1.0
    if not set_a or not set_b:      # if only one is empty, they are completely different
        return 0.0

    intersection = set_a & set_b
    union = set_a | set_b

    return len(intersection) / len(union)

def _normalize_url(url: str) -> str:
    """Normalize a URL for comparison by lowercasing and stripping fragments.
    This ensures that 'https://Example.com/Page#section' and 'https://example.com/page' are treated as the same URL.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # Rebuild without fragment and query - lowercase scheme + host
        normalized = f"{parsed.scheme.lower()}://{parsed.hostname or ''}{parsed.path.lower()}"
        return normalized
    except Exception:
        return url.lower()

def clean_and_deduplicate(results: list[SearchResult], similarity_threshold: float = SIMILARITY_THRESHOLD, max_results: int = MAX_RESULTS_AFTER_CLEANING) -> list[SearchResult]:
    """Clean, score, deduplicate, and rank search results.

    Pipeline steps:
      1. Clean text (strip HTML, normalize, truncate)
      2. Filter out results with content shorter than MIN_CONTENT_LENGTH
      3. Assign trust tiers based on domain analysis
      4. Remove exact-URL duplicates (keep the longer content)
      5. Remove near-duplicate content (Jaccard > threshold)
      6. Sort by trust tier (ascending = best first, 0 = most credible)
      7. Cap at max_results
    """
    if not results:
        logger.info("Cleaner received 0 results, returning empty list.")
        return []

    original_count = len(results)
    logger.info("Cleaner starting with %d raw results.", original_count)

    # clean text and filter short results
    cleaned: list[SearchResult] = []
    for r in results:
        clean_content = clean_text(r.content)
        if len(clean_content) < MIN_CONTENT_LENGTH:
            logger.debug("Filtered out short result (%d chars): %s", len(clean_content), r.url[:80])
            continue

        # Create a new SearchResult with the cleaned content and trust tier
        tier = assign_trust_tier(r.url)
        cleaned.append(         # pydantic is immutable by default, so we create a new instance with updated fields instead of modifying in place
            r.model_copy(
                update={
                    "content": clean_content,
                    "trust_tier": tier,
                }
            )
        )

    logger.info( "After cleaning and length filter: %d results (removed %d).", len(cleaned), original_count - len(cleaned))

    if not cleaned:
        return []

    # exact-URL deduplication
    url_map: dict[str, SearchResult] = {}
    for r in cleaned:
        norm_url = _normalize_url(r.url)
        if norm_url in url_map:
            # Keep the result with the longer content
            existing = url_map[norm_url]
            if len(r.content) > len(existing.content):
                url_map[norm_url] = r
        else:
            url_map[norm_url] = r

    url_deduped = list(url_map.values())        # only the search results - no need for the urls
    logger.info("After URL dedup: %d results (removed %d).", len(url_deduped), len(cleaned) - len(url_deduped))

    # near-duplicate content deduplication (Jaccard)
    content_deduped: list[SearchResult] = []
    for r in url_deduped:
        is_duplicate = False
        for kept in content_deduped:
            sim = jaccard_similarity(r.content, kept.content)
            if sim >= similarity_threshold:
                logger.debug(
                    "Near-duplicate removed (sim=%.2f): %s vs %s",
                    sim, r.url[:60], kept.url[:60],
                )
                is_duplicate = True
                break
        if not is_duplicate:
            content_deduped.append(r)

    logger.info( "After content dedup: %d results (removed %d).", len(content_deduped), len(url_deduped) - len(content_deduped))

    # sort by trust tier (0 first = most credible) then by content length (longer first)
    content_deduped.sort(key=lambda r: (r.trust_tier, -len(r.content)))
    final = content_deduped[:max_results]       # cap at max_results
    logger.info( "Cleaner complete: %d -> %d results.", original_count, len(final))

    return final