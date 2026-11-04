import asyncio
import httpx
import pytest

from app.config import settings


@pytest.mark.skipif( not settings.tavily_api_key, reason="TAVILY_API_KEY not set")      # tells pytest to skip this test if the Tavily API key is not set in the environment
def test_tavily_key_works() -> None:        # verify the Tavily API key can perform a search
    resp = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": "DuckDB benchmark",
            "max_results": 1,
        },
        timeout=15,     # tavily is faster than Nebius
    )
    assert resp.status_code == 200, f"Tavily returned {resp.status_code}: {resp.text[:200]}"        # in case of error, show the error msg
    data = resp.json()
    assert len(data.get("results", [])) >= 1, "Tavily returned zero results"
    print(f"Tavily OK: {data['results'][0]['title'][:60]}")