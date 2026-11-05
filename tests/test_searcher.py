import asyncio
import pytest

from app.agent.planner import plan
from app.agent.searcher import search
from app.config import settings

@pytest.mark.skipif(
    not settings.tavily_api_key or not settings.nebius_api_key,
    reason="API keys not set",
)

async def test_planner_and_searcher_e2e() -> None:    # verify planner output feeds into searcher and returns real results
    planner_output = await plan("Compare DuckDB vs ClickHouse")
    results = await search(planner_output.sub_queries)

    assert len(planner_output.sub_queries) >= 2, f"Planner produced only {len(planner_output.sub_queries)} sub-queries"
    assert len(results) >= 1, f"Searcher returned {len(results)} results"
    print(f"Planner: {len(planner_output.sub_queries)} sub-queries, Searcher: {len(results)} results")