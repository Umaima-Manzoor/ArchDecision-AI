"""
Tests the prompt building and source formatting logic (pure Python, no API calls).
The actual LLM call is tested via the E2E test in test_pipeline.py later.
"""

import pytest
from app.schemas import PlannerOutput, SubQuery, SearchResult
from app.agent.synthesizer import _format_sources, _build_messages

def _make_planner(tech_a: str = "PostgreSQL", tech_b: str = "MySQL", axes: list[str] = None) -> PlannerOutput:      # Factory for PlannerOutput test objects
    if axes is None:        # default arguments are evaluated once during function definition, not at every call, so the rest would have been appended (duplicate axes)
        axes = ["Performance", "Scalability"]
    sub_queries = [SubQuery(axis=a, query=f"{tech_a} vs {tech_b} {a}") for a in axes]
    return PlannerOutput(
        technology_a=tech_a,
        technology_b=tech_b,
        axes=axes,
        sub_queries=sub_queries,
    )


def _make_source(
    url: str = "https://postgresql.org/docs/performance",
    title: str = "PostgreSQL Performance Guide",
    content: str = "PostgreSQL supports advanced indexing including GIN and GiST for complex queries.",
    trust_tier: int = 0,
) -> SearchResult:      # factory for SearchResult test objects
    return SearchResult(
        url=url,
        title=title,
        content=content,
        trust_tier=trust_tier,
    )


class TestFormatSources:

    def test_formats_single_source(self):
        sources = [_make_source()]
        result = _format_sources(sources)
        assert "[SOURCE 1]" in result
        assert "postgresql.org" in result
        assert "official docs" in result       # trust tier 0 label

    def test_numbers_sources_sequentially(self):
        sources = [_make_source(url=f"https://example.com/{i}") for i in range(3)]
        result = _format_sources(sources)
        assert "[SOURCE 1]" in result
        assert "[SOURCE 2]" in result
        assert "[SOURCE 3]" in result

    def test_empty_sources(self):
        result = _format_sources([])
        assert "No sources available" in result

    def test_trust_labels(self):
        sources = [
            _make_source(url="https://a.com", trust_tier=0),
            _make_source(url="https://b.com", trust_tier=2),
            _make_source(url="https://c.com", trust_tier=4),
        ]
        result = _format_sources(sources)
        assert "official docs" in result
        assert "community" in result
        assert "low quality" in result

    def test_caps_content_at_1500(self):
        long_content = "x" * 3000
        sources = [_make_source(content=long_content)]
        result = _format_sources(sources)
        assert len(result) < 3000       # the content portion should be truncated


class TestBuildMessages:

    def test_returns_two_messages(self):
        planner = _make_planner()
        sources = [_make_source()]
        messages = _build_messages(planner, sources)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_includes_technologies_in_user_prompt(self):
        planner = _make_planner(tech_a="Redis", tech_b="Memcached")
        messages = _build_messages(planner, [_make_source()])
        user_content = messages[1]["content"]
        assert "Redis" in user_content
        assert "Memcached" in user_content

    def test_includes_axes_count(self):
        planner = _make_planner(axes=["Performance", "Scalability", "Security"])
        messages = _build_messages(planner, [_make_source()])
        user_content = messages[1]["content"]
        assert "3 axes x 2 technologies = 6 cells" in user_content

    def test_includes_sources(self):
        sources = [_make_source(url="https://redis.io/docs")]
        messages = _build_messages(_make_planner(), sources)
        user_content = messages[1]["content"]
        assert "redis.io" in user_content

    def test_system_prompt_forbids_fabrication(self):
        messages = _build_messages(_make_planner(), [_make_source()])
        system_content = messages[0]["content"]
        assert "Never fabricate" in system_content