<div align="center">

# <img src="app/static/favicon.svg" width="38" height="38" alt="ArchDecision Logo" style="vertical-align: middle; margin-right: 8px;"> ArchDecision AI

**Compare technologies with sourced, verifiable evidence.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.1-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Nebius](https://img.shields.io/badge/Nebius_Token_Factory-0A8754?style=for-the-badge&logo=openai&logoColor=white)](https://console.nebius.ai)
[![Tavily](https://img.shields.io/badge/Tavily_Search-4B8BBE?style=for-the-badge)](https://tavily.com)
[![Tests](https://img.shields.io/badge/Tests-65_Passed-0A8754?style=for-the-badge)](#-test-coverage)
[![License: MIT](https://img.shields.io/badge/License-MIT-F5A623?style=for-the-badge)](LICENSE)

An autonomous research agent that produces **Architecture Trade-Off Matrices** for software engineers. Every claim is backed by a real source. Every conflict is flagged. Nothing is fabricated.

[Watch the Demo Video 🎥](#)

</div>

<br>

> **Note:** To see the pipeline in action, [watch the 60-second demo video](#).

<details open>
<summary><b>📸 Product Preview (Click to toggle)</b></summary>
<br>

| 🔍 Live Streaming Pipeline | 📊 Interactive Matrix |
|:---:|:---:|
| <img src="docs/loading.png" width="400" alt="Loading state showing SSE stream"> | <img src="docs/results.png" width="400" alt="Full matrix results"> |
| **🛡️ Prompt Injection Defense** | **⚠️ Conflict Detection & Trace** |
| <img src="docs/guard.png" width="400" alt="Guard blocking injection"> | <img src="docs/trace.png" width="400" alt="Trace and conflicts"> |

</details>

---

## ✨ Why ArchDecision?

Software engineers waste hours comparing technologies across scattered blog posts, outdated benchmarks, and vendor marketing pages. ArchDecision does the heavy lifting:

* **Ask** a comparison question (e.g., "PostgreSQL vs MongoDB for real-time analytics").
* **Watch** the agent plan axes, search evidence, clean sources, and synthesize a matrix in ~30 seconds.
* **Decide** using visual confidence badges, inline citations, and conflict warnings.

❌ No hallucinated benchmarks.  
❌ No invented URLs.  
✅ Every single cell links directly to the source that proved it.

---

## 🧠 Interactive Architecture

ArchDecision uses a multi-agent pipeline orchestrated with asynchronous Python.

```mermaid
graph TD;
    User[👤 User Question] -->|POST /api/research| Guard{🛡️ Injection Guard}
    Guard -->|Clean| Planner(🤖 Query Planner)
    Guard -->|Malicious| Reject[❌ 400 Bad Request]
    Planner -->|Extracts 3-5 Axes| Searcher(🔍 Tavily Searcher)
    Searcher -->|Parallel Async Queries| Sub1[Axis 1]
    Searcher -->|Parallel Async Queries| Sub2[Axis 2]
    Searcher -->|Parallel Async Queries| Sub3[Axis 3]
    Sub1 --> Cleaner(🧹 Cleaner & Dedup)
    Sub2 --> Cleaner
    Sub3 --> Cleaner
    Cleaner -->|HTML Strip, Jaccard Filter| Tiers[🥇 Trust Tiers 0-4]
    Tiers --> Synthesizer(🧠 Synthesizer Agent)
    Synthesizer -->|Validates Sources| Output[📊 Trade-Off Matrix]
    Output -->|Server-Sent Events| UI[✨ Interactive Web UI]
    
    classDef agent fill:#0a8754,stroke:#076b42,stroke-width:2px,color:#fff;
    classDef search fill:#4B8BBE,stroke:#3b76a6,stroke-width:2px,color:#fff;
    class Planner,Synthesizer agent;
    class Searcher,Sub1,Sub2,Sub3 search;
```

### 🥇 Trust Tier Verification
The Cleaner automatically ranks sources by domain credibility before they reach the synthesis layer:

| Tier | Trust Level | Source Types | Examples |
|:---:|---|---|---|
| **0** | 🟢 **Highest** | Official Documentation | `postgresql.org`, `redis.io` |
| **1** | 🟢 **High** | Cloud Vendors / Tech Blogs | `aws.amazon.com`, `netflixtechblog.com` |
| **2** | 🟡 **Medium** | Reputable Community | `stackoverflow.com`, `github.com` |
| **3** | 🟠 **Low** | General Blogs | `medium.com`, unknown domains |
| **4** | 🔴 **Untrusted** | SEO Farms / Aggregators | `tutorialspoint.com`, `w3schools.com` |

---

## ⚡ Core Capabilities

| Feature | Implementation | Benefit |
|---|---|---|
| **Verifiable Citations** | Every claim links directly to its origin URL. Assigns Confidence (High/Medium/Low) and tags claims (Fact/Inference). | Complete transparency without hallucinated URLs. |
| **Live SSE Streaming** | Real-time Server-Sent Events push execution step updates to the UI as they complete. | Instant visual feedback during agent reasoning. |
| **Dynamic Axis Planning** | Query Planner extracts dynamic evaluation criteria tailored to the technologies queried. | Removes static template constraints. |
| **Multi-Model Resilience** | Primary inference via `Qwen3-235B` with automatic fallback to `Gemma-3-27B`. | High reliability and operational stability. |
| **Injection Guard** | Regex and length boundary filters neutralize prompt injection attempts before pipeline execution. | Reliable security against malicious inputs. |

---

## 🛠️ Quick Start

<details>
<summary><b>1. Prerequisites (Click to expand)</b></summary>

* **Python 3.12+**
* A **[Nebius Token Factory](https://console.nebius.ai)** API key.
* A **[Tavily](https://tavily.com)** API key.
</details>

<details open>
<summary><b>2. Installation & Setup</b></summary>

```bash
# Clone the repository
git clone https://github.com/Umaima-Manzoor/ArchDecision-AI.git
cd ArchDecision-AI

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
```
👉 *Open `.env` and configure your `NEBIUS_API_KEY` and `TAVILY_API_KEY`.*
</details>

<details open>
<summary><b>3. Run the App</b></summary>

```bash
uvicorn app.main:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** to view the interface.
</details>

---

## 💸 Cost Efficiency

Filtering raw content in the `Cleaner` module minimizes token overhead before LLM processing:

| Model | Input Cost | Output Cost | Average Query Cost |
|---|---|---|---|
| **Qwen3-235B-A22B** | $0.20 / 1M | $0.60 / 1M | ~7,000 tokens ≈ **$0.002** |
| **Gemma-3-27B** *(Fallback)* | $0.10 / 1M | $0.30 / 1M | ~7,000 tokens ≈ **$0.001** |

---

## 🧪 Test Coverage

ArchDecision includes test suites covering schema validation, HTML parsing, Jaccard deduplication, prompt injection defense, and End-to-End integration.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```
<kbd>65 passed in ~10.13s</kbd>

---

## 📚 API Reference

<details>
<summary><b><code>POST /api/research</code> (JSON Response)</b></summary>

Run the full pipeline synchronously.

**Request:**
```json
{ "question": "Compare DuckDB vs ClickHouse for embedded analytics" }
```

**Response Extract:**
```json
{
  "matrix": {
    "technology_a": "DuckDB",
    "cells": [
      {
        "axis": "Query Performance",
        "claim": "DuckDB processes analytical queries on local data in milliseconds...",
        "source_url": "https://duckdb.org/why_duckdb",
        "confidence": "H"
      }
    ]
  },
  "latency_seconds": 28.4,
  "token_usage": {
    "total_tokens": 7000,
    "estimated_cost_usd": 0.0021
  }
}
```
</details>

<details>
<summary><b><code>GET /api/research/stream</code> (SSE Streaming)</b></summary>

Stream live Server-Sent Events to track pipeline execution progress.

```text
GET /api/research/stream?question=PostgreSQL+vs+MongoDB
```
</details>

---

<div align="center">
  <p>ArchDecision AI &bull; Open Source Software</p>
  <p>Released under the <a href="LICENSE">MIT License</a>.</p>
</div>