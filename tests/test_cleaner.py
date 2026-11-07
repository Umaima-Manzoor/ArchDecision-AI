import pytest
from app.schemas import SearchResult
from app.agent.cleaner import (
    clean_text, assign_trust_tier, jaccard_similarity, clean_and_deduplicate, _normalize_url,
)

def _make_result(
    url: str = "https://example.com/article",
    title: str = "Test Article",
    snippet: str = "This is a test snippet with enough words to pass the minimum length filter for the cleaner pipeline.",
    trust_tier: int = 3,
) -> SearchResult:
    """Factory function to create SearchResult objects for testing."""
    return SearchResult(
        url=url,
        title=title,
        snippet=snippet,
        trust_tier=trust_tier,
    )


class TestCleanText:

    def test_strips_html_tags(self):
        raw = "<p>This is <b>bold</b> and <a href='x'>linked</a>.</p>"
        result = clean_text(raw)
        assert "<" not in result
        assert ">" not in result
        assert "bold" in result

    def test_collapses_whitespace(self):
        raw = "hello    \n\n   world   \t  test"
        result = clean_text(raw)
        assert result == "hello world test"

    def test_truncates_long_text(self):
        long_text = "word " * 1000
        result = clean_text(long_text, max_length=100)
        assert len(result) <= 110       # allow slightly more because of ellipses and word boundary
        assert result.endswith("...")

    def test_truncates_at_word_boundary(self):
        text = "a" * 50 + " " + "b" * 60 + " end"
        result = clean_text(text, max_length=100)
        assert "..." in result

    def test_removes_boilerplate(self):
        raw = "Great article about databases. Click here to subscribe to our newsletter for more."
        result = clean_text(raw)
        assert "newsletter" not in result.lower()
        assert "databases" in result.lower()

    def test_empty_string(self):
        assert clean_text("") == ""


class TestAssignTrustTier:

    def test_tier_0_official_docs(self):
        assert assign_trust_tier("https://www.postgresql.org/docs/16/performance.html") == 0
        assert assign_trust_tier("https://redis.io/docs/data-types/") == 0
        assert assign_trust_tier("https://kubernetes.io/docs/concepts/") == 0

    def test_tier_0_subdomain(self):
        assert assign_trust_tier("https://docs.mongodb.com/manual/") == 0

    def test_tier_0_prefix(self):
        assert assign_trust_tier("https://docs.someunknowndb.com/guide") == 0

    def test_tier_1_cloud_vendor(self):
        assert assign_trust_tier("https://aws.amazon.com/rds/postgresql/") == 1
        assert assign_trust_tier("https://cloud.google.com/sql/docs") == 1

    def test_tier_2_community(self):
        assert assign_trust_tier("https://stackoverflow.com/questions/12345") == 2
        assert assign_trust_tier("https://github.com/redis/redis") == 2

    def test_tier_3_blog_platform(self):
        assert assign_trust_tier("https://medium.com/@user/postgres-tips") == 3
        assert assign_trust_tier("https://dev.to/user/redis-vs-memcached") == 3

    def test_tier_3_unknown_domain(self):
        assert assign_trust_tier("https://random-tech-blog.xyz/article") == 3

    def test_tier_4_seo_farm(self):
        assert assign_trust_tier("https://www.tutorialspoint.com/postgresql/index.htm") == 4
        assert assign_trust_tier("https://www.geeksforgeeks.org/postgresql-tutorial/") == 4

    def test_empty_url(self):
        assert assign_trust_tier("") == 4

    def test_www_prefix_stripped(self):
        assert assign_trust_tier("https://www.postgresql.org/about/") == 0


class TestJaccardSimilarity:

    def test_identical_texts(self):
        text = "PostgreSQL supports JSONB indexing for fast document queries"
        assert jaccard_similarity(text, text) == 1.0

    def test_completely_different(self):
        a = "apple banana cherry"
        b = "dog elephant frog"
        assert jaccard_similarity(a, b) == 0.0

    def test_partial_overlap(self):
        a = "PostgreSQL supports JSONB indexing for fast queries"
        b = "PostgreSQL supports JSONB storage but not indexing"
        sim = jaccard_similarity(a, b)
        assert 0.3 < sim < 0.8

    def test_empty_strings(self):
        assert jaccard_similarity("", "") == 1.0
        assert jaccard_similarity("hello world", "") == 0.0

    def test_ignores_short_words(self):
        a = "a database is used to store data"
        b = "the database will store your data"
        sim = jaccard_similarity(a, b)
        assert sim > 0.3


class TestNormalizeUrl:

    def test_lowercases(self):
        assert _normalize_url("HTTPS://Example.COM/Page") == "https://example.com/page"

    def test_strips_fragment(self):
        result = _normalize_url("https://example.com/page#section-2")
        assert "#" not in result

    def test_empty_url(self):
        assert _normalize_url("") == ""


class TestCleanAndDeduplicate:

    def test_empty_input(self):
        assert clean_and_deduplicate([]) == []

    def test_filters_short_snippets(self):
        results = [
            _make_result(snippet="Too short."),
            _make_result(
                url="https://postgresql.org/good",
                snippet="This is a properly long snippet about PostgreSQL performance tuning that should survive the length filter easily.",
            ),
        ]
        output = clean_and_deduplicate(results)
        assert len(output) == 1
        assert "postgresql.org" in output[0].url

    def test_removes_exact_url_duplicates(self):
        results = [
            _make_result(
                url="https://example.com/page",
                snippet="Short snippet about the topic that passes the filter.",
            ),
            _make_result(
                url="https://example.com/page",
                snippet="This is a much longer snippet about the same topic that should be kept because it has more content for the synthesizer to work with.",
            ),
        ]
        output = clean_and_deduplicate(results)
        assert len(output) == 1
        assert "much longer" in output[0].snippet

    def test_removes_near_duplicate_content(self):
        base = "PostgreSQL offers excellent JSONB support with GIN indexing for document-style queries and nested data access patterns"
        results = [
            _make_result(url="https://a.com/1", snippet=base),
            _make_result(
                url="https://b.com/2",
                snippet=base + " and also supports full-text search capabilities",
            ),
        ]
        output = clean_and_deduplicate(results, similarity_threshold=0.5)
        assert len(output) == 1

    def test_keeps_different_content(self):
        results = [
            _make_result(
                url="https://a.com/1",
                snippet="PostgreSQL is a relational database with strong ACID compliance and advanced indexing features.",
            ),
            _make_result(
                url="https://b.com/2",
                snippet="Redis is an in-memory key-value store optimized for low-latency caching and real-time pub/sub messaging.",
            ),
        ]
        output = clean_and_deduplicate(results)
        assert len(output) == 2

    def test_sorts_by_trust_tier(self):
        results = [
            _make_result(
                url="https://medium.com/blog-post",
                snippet="A blog post about database performance that is long enough to pass the minimum length filter easily.",
            ),
            _make_result(
                url="https://www.postgresql.org/docs/performance",
                snippet="Official PostgreSQL documentation about performance tuning and query optimization strategies for production.",
            ),
        ]
        output = clean_and_deduplicate(results)
        assert len(output) == 2
        assert output[0].trust_tier == 0
        assert output[1].trust_tier == 3

    def test_caps_at_max_results(self):
        results = [
            _make_result(
                url=f"https://example.com/article-{i}",
                snippet=f"Unique article number {i} about database architecture and performance tuning strategies for modern applications.",
            )
            for i in range(25)
        ]
        output = clean_and_deduplicate(results, max_results=5)
        assert len(output) == 5

    def test_reassigns_trust_tiers(self):
        results = [
            _make_result(
                url="https://www.postgresql.org/docs/",
                snippet="Official docs about PostgreSQL configuration and tuning parameters for production database deployments.",
                trust_tier=4,
            ),
        ]
        output = clean_and_deduplicate(results)
        assert output[0].trust_tier == 0