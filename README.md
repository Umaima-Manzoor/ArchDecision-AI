# ArchDecision AI

Autonomous research agent that helps software engineers make technical trade-off
decisions in minutes instead of hours. Ask a comparison question, get a sourced
Architecture Trade-Off Matrix where every claim links to the evidence that
supports it.

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/archdecision-ai.git
cd archdecision-ai
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Nebius and Tavily API keys
uvicorn app.main:app --reload --port 8000