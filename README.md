# ArchDecision AI

Autonomous research agent that helps software engineers make technical trade-off
decisions in minutes instead of hours. Ask a comparison question, get a sourced
Architecture Trade-Off Matrix where every claim links to the evidence that
supports it.

## Quick Start

```bash
git clone https://github.com/Umaima-Manzoor/ArchDecision-AI.git
cd ArchDecision-AI
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Nebius and Tavily API keys
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## Required API Keys

| Service | Where to Get | Free Tier |
|---------|-------------|-----------|
| Nebius Token Factory | console.nebius.ai | Hackathon credits |
| Tavily Search | app.tavily.com | 1,000 searches/month |
| Langfuse (optional) | cloud.langfuse.com | 50K observations/month |

## Architecture

```
User Query
    |
    v
Step 1: Query Planner (Nebius Llama 3.1 70B)
    Decomposes into 3 to 5 adaptive research axes
    |
    v
Step 2: Live Search (Tavily API)
    Parallel searches per sub-query
    |
    v
Step 3: Clean and Deduplicate (Python)
    URL dedup, trust tier scoring
    |
    v
Step 4: Synthesizer (Nebius Llama 3.1 70B)
    Maps claims to sources, detects conflicts,
    flags insufficient data
    |
    v
Output: Architecture Trade-Off Matrix
    Inline citations, confidence indicators,
    conflict badges, execution trace
```

## Target User

Software engineers, platform engineers, and system architects evaluating
competing technologies (databases, frameworks, infrastructure tools).

## Tech Stack

- **Backend:** Python 3.12, FastAPI, httpx, Pydantic
- **Inference:** Nebius Token Factory (meta-llama/Meta-Llama-3.1-70B-Instruct)
- **Search:** Tavily Search API
- **Observability:** Langfuse (optional)
- **Frontend:** HTML, Tailwind CSS (CDN), vanilla JavaScript
- **Deployment:** Qoddi (free tier) or local uvicorn

## Limitations

- Single-turn research only. Follow-up deep dives are planned but not
  yet implemented.
- Source credibility scoring is domain-based, not content-verified.
- The agent makes one round of Tavily searches per query. Multi-round
  refinement is a future improvement.
- Numerical scores in the radar chart export are LLM-derived summaries,
  not measured benchmarks.

## License

MIT