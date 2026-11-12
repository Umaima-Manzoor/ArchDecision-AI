"""
Takes the PlannerOutput (technologies + axes) and cleaned SearchResults, then calls the Nebius LLM to generate a structured TradeOffMatrix with:
  - One MatrixCell per (axis, technology) combination
  - Confidence levels (H/M/L) and tags (FACT/INFERENCE/UNVERIFIED)
  - Conflict badges when credible sources disagree
  - Insufficient data flags when sources don't cover an axis
Uses the same retry + model fallback pattern as the Planner.
"""

import json
import logging
import httpx

from app.config import settings
from app.schemas import PlannerOutput, SearchResult, TradeOffMatrix
from app.agent.tracer import Tracer       # for optional token tracking

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 90        # synthesizer needs more time than planner (larger prompt + response)
MAX_RETRIES = 3
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"


def _format_sources(sources: list[SearchResult]) -> str:
    """Format cleaned sources into a numbered list for the LLM prompt.
    Each source gets a number, URL, title, trust tier, and content snippet.
    The LLM uses these numbers to cite sources in its claims.
    """
    if not sources:
        return "No sources available."

    parts: list[str] = []
    for i, s in enumerate(sources, start=1):
        trust_label = {0: "official docs", 1: "cloud vendor", 2: "community", 3: "blog/unknown", 4: "low quality"}
        label = trust_label.get(s.trust_tier, "unknown")
        parts.append(
            f"[SOURCE {i}]\n"
            f"URL: {s.url}\n"
            f"Title: {s.title}\n"
            f"Trust: {s.trust_tier} ({label})\n"
            f"Content: {s.content[:1500]}"       # cap per-source content to stay in token budget
        )
    return "\n\n".join(parts)


def _build_messages(planner: PlannerOutput, sources: list[SearchResult]) -> list[dict]:
    """Build the system + user messages for the Synthesizer LLM call.
    The system message defines the role and rules - the user message provides the specific technologies, axes, and sources.
    """
    system_prompt = (
        "You are an expert software architect producing a factual Architecture Trade-Off Matrix.\n"
        "Rules:\n"
        "1. ONLY use the sources provided below. Never fabricate URLs, benchmarks, or claims.\n"
        "2. For each axis and each technology, produce exactly one claim backed by the best source.\n"
        "3. Assign confidence: H if backed by official docs or benchmarks, M if backed by reputable community sources, L if based on inference or weak evidence.\n"
        "4. Tag each claim: FACT if directly stated in the source, INFERENCE if reasonably derived from the source, UNVERIFIED if the source is weak or the claim is speculative.\n"
        "5. If two credible sources (trust <= 2) disagree on the same axis, create a conflict badge.\n"
        "6. If no credible source covers an axis for a technology, add that axis to insufficient_data.\n"
        "7. source_url must be an exact URL from the provided sources. Do not modify or invent URLs.\n"
        "8. Respond with valid JSON only. No markdown, no explanation, no code fences."
    )

    formatted_sources = _format_sources(sources)
    axes_str = ", ".join(planner.axes)

    user_prompt = (
        f"Compare: {planner.technology_a} vs {planner.technology_b}\n"
        f"Axes to evaluate: {axes_str}\n\n"
        f"Sources ({len(sources)} total):\n"
        f"{formatted_sources}\n\n"
        "Generate the TradeOffMatrix as JSON with this exact structure:\n"
        f'''{{
  "technology_a": "{planner.technology_a}",
  "technology_b": "{planner.technology_b}",
  "cells": [
    {{
      "axis": "Performance",
      "technology": "{planner.technology_a}",
      "claim": "Specific factual claim about performance",
      "source_url": "exact URL from sources above",
      "source_title": "title of the source",
      "confidence": "H",
      "tag": "FACT"
    }}
  ],
  "conflicts": [
    {{
      "axis": "Performance",
      "description": "Source A says X but Source B says Y",
      "source_a_url": "url",
      "source_b_url": "url"
    }}
  ],
  "insufficient_data": ["AxisName"]
}}'''
        f"\n\nGenerate cells for ALL combinations: {len(planner.axes)} axes x 2 technologies = {len(planner.axes) * 2} cells."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def synthesize_matrix(planner_output: PlannerOutput, sources: list[SearchResult], tracer: Tracer | None = None) -> TradeOffMatrix:     #  added optional tracer at the end
    """Generate a TradeOffMatrix from planner output and cleaned sources.
    Calls the Nebius LLM with the sources and axes, parses the JSON response
    into a validated TradeOffMatrix Pydantic model.
    """
    messages = _build_messages(planner_output, sources)
    models = [settings.nebius_model, settings.nebius_fallback_model]

    for attempt in range(1, MAX_RETRIES + 1):
        model = models[0] if attempt == 1 else models[1]       # primary first, fallback on retry
        logger.info("Synthesizer attempt %d/%d using model: %s", attempt, MAX_RETRIES, model)

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{NEBIUS_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.nebius_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.1,       # low temperature for factual consistency
                        "max_tokens": 4096,        # matrix can be large with many axes
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()

            data = response.json()

            if tracer and "usage" in data:        # log token usage if tracer exists and API returned usage
                tracer.add_usage(data["usage"].get("prompt_tokens", 0), data["usage"].get("completion_tokens", 0))

            raw_text = data["choices"][0]["message"]["content"]

            # strip markdown code fences if the model wraps JSON in ```json ... ```
            if raw_text.strip().startswith("```"):
                lines = raw_text.strip().split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw_text = "\n".join(lines)

            parsed = json.loads(raw_text)           # json catches syntax errors
            matrix = TradeOffMatrix(**parsed)       # pydantic validates the structure

            logger.info(
                "Synthesizer complete: %d cells, %d conflicts, %d insufficient axes",
                len(matrix.cells),
                len(matrix.conflicts),
                len(matrix.insufficient_data),
            )
            return matrix

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.warning("Synthesizer HTTP %d on attempt %d: %s", status, attempt, e.response.text[:200])
            if status in (401, 403):
                raise       # auth errors won't be fixed by retrying
        except (json.JSONDecodeError, KeyError, ValueError) as e:       # KeyError if "choices" or "message" is missing, ValueError if Pydantic validation fails
            logger.warning("Synthesizer parse error on attempt %d: %s", attempt, e)
        except httpx.RequestError as e:     # catches DNS failures, refused connections timeouts and other network errors
            logger.warning("Synthesizer network error on attempt %d: %s", attempt, str(e)[:100])
        except Exception as e:
            logger.warning("Synthesizer unexpected error on attempt %d: %s", attempt, e)

    raise RuntimeError(f"Synthesizer failed after {MAX_RETRIES} attempts with all models.")