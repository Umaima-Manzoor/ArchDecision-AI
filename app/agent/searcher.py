import asyncio          # for concurrent execution
import logging
from typing import Any
import httpx
from app.config import settings
from app.schemas import SearchResult, SubQuery

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TIMEOUT_SECONDS = 15            # faster than Nebius so 15 sec is plenty
MAX_RETRIES = 3
MAX_RESULTS_PER_QUERY = 5


async def _search_single(client: httpx.AsyncClient, sub_query: SubQuery) -> list[SearchResult]:    # Run one Tavily search for a single sub-query
    payload: dict[str, Any] = {
        "api_key": settings.tavily_api_key,
        "query": sub_query.query,
        "max_results": MAX_RESULTS_PER_QUERY,
        "search_depth": "basic",        # fast, cheap search mode
        "include_answer": False,        # no AI generated summaries
    }

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.post(           # sending request to Tavily
                TAVILY_SEARCH_URL,
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()         # converts 4xx/5xx responses into errors
            data: dict[str, Any] = response.json()

            raw_results: list[dict[str, Any]] = data.get("results", [])
            results: list[SearchResult] = []

            for item in raw_results:
                results.append(         # trust_tier is set in cleaner, not here
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        published_date=item.get("published_date", ""),
                    )
                )

            logger.info("Tavily search OK for axis '%s': %d results", sub_query.axis, len(results))
            return results

        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            logger.warning("Tavily HTTP %d on attempt %d for '%s': %s", status, attempt, sub_query.axis, exc.response.text[:150])

            if status in (401, 403):
                raise
            if status == 429:
                wait = 2 ** attempt
                logger.info("Tavily rate limited. Waiting %ds.", wait)
                await asyncio.sleep(wait)

        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning("Tavily timeout on attempt %d for '%s'", attempt, sub_query.axis )

        except Exception as exc:
            last_error = exc
            logger.error("Tavily unexpected error for '%s': %s", sub_query.axis, str(exc))
            break

    logger.warning("Tavily search failed for axis '%s' after %d attempts: %s", sub_query.axis, MAX_RETRIES, last_error)
    return []


async def search(sub_queries: list[SubQuery]) -> list[SearchResult]:        # Run parallel Tavily searches for all sub-queries
    logger.info("Searcher starting with %d sub-queries", len(sub_queries))

    async with httpx.AsyncClient() as client:
        tasks = [_search_single(client, sq) for sq in sub_queries]
        all_results_nested = await asyncio.gather(*tasks)       # runs them all concurrently - returns in order of input

    flat_results: list[SearchResult] = []           # converts nested list to flat 
    for result_list in all_results_nested:
        flat_results.extend(result_list)

    logger.info(
        "Searcher complete: %d total results from %d queries",
        len(flat_results), len(sub_queries),
    )
    return flat_results