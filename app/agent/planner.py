import asyncio
import json 
import logging
from typing import Any      # for type hints on untyped dictionaries

import httpx        # for async HTTP requests as FastAPI is async

from app.config import settings
from app.schemas import PlannerOutput

logger = logging.getLogger(__name__)        # easier to dintinguish planner logs from searcher or synthesizer logs

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
TIMEOUT_SECONDS = 30        # enough since Nebius API can take 10-30 sec for large LLMs to respond
MAX_RETRIES = 3     # balancing reliability and not making the user wait too long 

PLANNER_SYSTEM_PROMPT = """\
You are a research query planner for an architecture trade-off analysis agent.

Your job: given a user question comparing two technologies, decompose it into
a structured research plan with adaptive axes and search sub-queries.

Rules:
1. Identify the two specific technologies being compared. If the user is vague, infer the most likely pair from context.
2. Generate 3 to 5 research axes that are most relevant to THIS specific comparison. Do NOT use a fixed set of axes. Adapt to the question.
   Examples of possible axes: Performance, Memory Footprint, Scalability, License and Cost, Operational Complexity, Ecosystem Maturity, Community Support, Data Model Fit, Deployment Model, Security, Known Production Issues, Learning Curve, Team Size Fit.
3. For each axis, write one specific Tavily search query that will retrieve the most relevant evidence. Include the technology names and the year in the query for freshness.
4. Return ONLY valid JSON. No markdown, no explanation, no code fences.

Output schema (return exactly this structure):
{
  "technology_a": "Name of first technology",
  "technology_b": "Name of second technology",
  "axes": ["Axis 1", "Axis 2", "Axis 3"],
  "sub_queries": [
    {"axis": "Axis 1", "query": "specific search query for Tavily"},
    {"axis": "Axis 2", "query": "specific search query for Tavily"},
    {"axis": "Axis 3", "query": "specific search query for Tavily"}
  ]
}
"""


async def _call_nebius(client: httpx.AsyncClient, user_question: str, model: str) -> str:       # makes the actual HTTP POST request to Nebius Token Factory
    headers = {
        "Authorization": f"Bearer {settings.nebius_api_key}",       # bearer is standard for API keys authentication in HTTP headers
        "Content-Type": "application/json",     # we are sending JSON data in the request body
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_question},
        ],
        "temperature": 0.1,         # keeps output deterministic and focused on factual information rather than creative writing
        "max_tokens": 1024,         # json responses are usually 300-500 tokena so safe
    }
    response = await client.post(               # sends the reuqest
        f"{NEBIUS_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()             # in case of 4xx / 5xx
    data: dict[str, Any] = response.json()
    content: str = data["choices"][0]["message"]["content"]
    return content


def _extract_json(text: str) -> dict[str, Any]:     # cleans the LLm's raw output and extracts the JSON part, removing any markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):           # replace ```` by newlines
        lines = cleaned.split("\n")
        lines = [
            line for line in lines
            if not line.strip().startswith("```")
        ]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


async def plan(question: str) -> PlannerOutput:     # Decompose a user question into a structured research plan     (called by main.py)
    logger.info("Planner starting for question: %s", question[:80])
    last_error: Exception | None = None     # final error msg has the most recent error for debugging if all attempts fail

    for attempt in range(1, MAX_RETRIES + 1):
        model = settings.nebius_model if attempt == 1 else settings.nebius_fallback_model      # on first 2 tries use primary model, on last try use fallback model (if primary model is down or rate limited)
        logger.info("Planner attempt %d/%d using model %s", attempt, MAX_RETRIES, model)

        try:
            async with httpx.AsyncClient() as client:       # create a new async HTTP client for each attempt to avoid connection issues
                raw_content = await _call_nebius(client, question, model)

            logger.debug("Raw LLM output: %s", raw_content[:200])

            parsed = _extract_json(raw_content)
            result = PlannerOutput.model_validate(parsed)

            logger.info("Planner succeeded: %s vs %s, %d axes",
                result.technology_a, result.technology_b, len(result.axes))
            return result

        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            logger.warning("Planner HTTP error %d on attempt %d: %s", status, attempt, exc.response.text[:200])

            if status == 429:           # waiting if rate limited but raising immediately for other 4xx errors
                wait = 2 ** attempt
                logger.info("Rate limited. Waiting %d seconds.", wait)
                await asyncio.sleep(wait)
            elif status >= 500:
                await asyncio.sleep(2)
            else:
                raise

        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning("Planner JSON parse error on attempt %d: %s", attempt, str(exc)[:200])

        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning("Planner timeout on attempt %d", attempt)

        except Exception as exc:
            last_error = exc
            logger.error("Planner unexpected error on attempt %d: %s", attempt, str(exc))
            break

    error_msg = f"Planner failed after {MAX_RETRIES} attempts: {last_error}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)