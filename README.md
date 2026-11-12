# ArchDecision AI

An autonomous research agent that produces sourced, verifiable Architecture Trade-Off Matrices for software engineers comparing technologies.

Built for the [ODSC AI x Nebius Hackathon](https://odsc.com).

## What It Does

You ask a question like "Compare PostgreSQL vs MongoDB for real-time analytics." The agent:

1. Decomposes the question into 3 to 5 research axes (Performance, Scalability, Operational Complexity, etc.)
2. Runs parallel Tavily searches for each axis
3. Deduplicates results, strips boilerplate, and assigns trust tiers (official docs > cloud vendor > community > blog > SEO farm)
4. Synthesizes a structured matrix with inline citations, confidence levels (H/M/L), and conflict badges when credible sources disagree
5. Returns the full matrix with an execution trace showing every step

No fabricated benchmarks. No invented URLs. Every claim links to a real source.

## Tech Stack

| Layer | Tool |
|-------|------|
| Backend | FastAPI (Python 3.12) |
| LLM | Nebius Token Factory (Qwen3-235B-A22B primary, Gemma-3-27B fallback) |
| Search | Tavily Search API |
| Validation | Pydantic v2 |
| HTTP | httpx (async) |
| Deployment | Docker (local) |

## Architecture

```
User Question
     |
     v
[Planner] -- Nebius LLM decomposes into axes + sub-queries
     |
     v
[Searcher] -- Tavily fetches 5 results per sub-query (parallel)
     |
     v
[Cleaner] -- HTML strip, dedup (URL + Jaccard similarity), trust tier assignment
     |
     v
[Synthesizer] -- Nebius LLM builds matrix from cleaned sources
     |
     v
[Tracer] -- Timestamped execution log returned with response
```

## Quick Start

### Prerequisites

- Python 3.12+
- A [Nebius Token Factory](https://console.nebius.ai) API key (free trial credits)
- A [Tavily](https://tavily.com) API key (1,000 free searches/month)

### Setup

```bash
git clone https://github.com/Umaima-Manzoor/ArchDecision-AI.git
cd ArchDecision-AI

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your API keys
```

### Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) for the frontend or [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

## API Reference

### POST /api/research

Run the full research pipeline.

**Request:**

```json
{
  "question": "Compare DuckDB vs ClickHouse for embedded analytics"
}
```

**Response:**

```json
{
  "matrix": {
    "technology_a": "DuckDB",
    "technology_b": "ClickHouse",
    "cells": [
      {
        "axis": "Query Performance",
        "technology": "DuckDB",
        "claim": "DuckDB processes analytical queries on local data in milliseconds due to its columnar vectorized engine.",
        "source_url": "https://duckdb.org/why_duckdb",
        "source_title": "Why DuckDB",
        "confidence": "H",
        "tag": "FACT"
      }
    ],
    "conflicts": [],
    "insufficient_data": []
  },
  "trace": [
    {"timestamp": "2026-11-08T15:56:42+00:00", "step": "planned", "detail": "DuckDB vs ClickHouse, 5 axes"}
  ],
  "total_sources": 15,
  "latency_seconds": 15.43
}
```

### GET /health

Returns `{"status": "ok", "version": "0.1.0"}`.

## Project Structure

```
ArchDecision-AI/
  app/
    agent/
      planner.py       # Step 1: LLM query decomposition
      searcher.py      # Step 2: Tavily parallel search
      cleaner.py       # Step 3: Dedup + trust tiers
      synthesizer.py   # Step 4: LLM matrix generation
      tracer.py        # Step 5: Execution logging
      guard.py         # Input validation and prompt injection defense
    static/
      index.html       # Frontend SPA
    config.py          # Settings (Pydantic BaseSettings)
    schemas.py         # Pydantic models for request/response
    main.py            # FastAPI app + /api/research endpoint
  tests/
    test_planner.py
    test_searcher.py
    test_cleaner.py
    test_synthesizer.py
    test_tracer.py
    test_guard.py
    test_keys.py
  Dockerfile
  requirements.txt
  .env.example
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

59 tests covering all pipeline stages: schema validation, HTML cleaning, trust tier assignment, Jaccard deduplication, source formatting, prompt construction, trace logging, prompt injection defense, and end-to-end planner-searcher integration.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEBIUS_API_KEY` | Yes | Nebius Token Factory bearer token |
| `TAVILY_API_KEY` | Yes | Tavily search API key |
| `CORS_ORIGINS` | No | Comma-separated list of allowed origins. Leave blank to disable cross-origin requests entirely. |

## License

MIT