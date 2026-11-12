import json         # SSE needs to manually format - FastAPI can't do that here
import logging
import time
from contextlib import asynccontextmanager      # creates startup/shutdown hooks for FastAPI
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query       # Query to validate url query parameters
from fastapi.middleware.cors import CORSMiddleware      # for deployment
from fastapi.responses import FileResponse, StreamingResponse   # sends data in chunks instead of all at once
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import AgentResponse, QueryRequest, TokenUsage
from app.agent.planner import plan                      # Nebius decomposes the question
from app.agent.searcher import search                   # Tavily calls for each sub-query
from app.agent.cleaner import clean_and_deduplicate     # cleaning, deduplicating, tiers
from app.agent.synthesizer import synthesize_matrix     # Nebius build the matrix from sources
from app.agent.tracer import Tracer                     # logging each pipeline step 
from app.agent.guard import check_injection             # prompt injection defense

logging.basicConfig(
    level=logging.INFO,     # minimum level to log (DEBUG, INFO, WARNING, ERROR, CRITICAL)  - everything other than DEUG is logged
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",     # current datetime, severity level, logger name (app.main, app.agent.planner), message
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Approximate Nebius Token Factory pricing per 1M tokens for Qwen3-235B (update if pricing changes)
INPUT_COST_PER_M = 0.20         # $0.20 per million input tokens
OUTPUT_COST_PER_M = 0.60        # $0.60 per million output tokens (output costs ~3x more than input)


@asynccontextmanager        # before and after section separated by yield
async def lifespan(app: FastAPI):       # Validate configuration on startup
    try:
        settings.validate_required_keys()
    except ValueError as exc:
        logger.warning("Startup validation: %s", exc)
        logger.warning("The /api/research endpoint will not work until keys are set.")
    logger.info("ArchDecision AI server started")
    yield
    logger.info("ArchDecision AI server shutting down")


app = FastAPI(
    title="ArchDecision AI",
    description="Research agent for architecture trade-off analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow only the origins listed in CORS_ORIGINS. Wildcarding here would expose
# the endpoint to any website and let it send authenticated requests cross-origin.
allowed_origins = [
    o.strip() for o in settings.cors_origins.split(",") if o.strip()
] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def format_sse(data: dict) -> str:              # formats a dictionary as a Server-Sent Event string
    return f"data: {json.dumps(data)}\n\n"      # SSE protocol requires "data: " prefix and double newline

@app.get("/health")
async def health() -> dict[str, str]:       # Health check endpoint for deployment platforms
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")       # when someone visits the root url with a GET request, run this function 
async def root() -> FileResponse:           # an HTTP response that returns a file (index.html) to the client
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not built yet")
    return FileResponse(str(index_path))        # sends index.html to browser


@app.post("/api/research", response_model=AgentResponse)        # when someone sends a POST request to /api/research, run this function and return an AgentResponse schema
async def research(request: QueryRequest) -> AgentResponse:     # Run the full research agent pipeline
    logger.info("Research request received: %s", request.question[:80])

    # Check for prompt injection before running the pipeline
    injection = check_injection(request.question)
    if injection:
        logger.warning("Prompt injection blocked: %s (pattern: %s)", request.question[:80], injection)
        raise HTTPException(status_code=400, detail="Your query appears to contain instructions that conflict with the agent's purpose. Please ask a technology comparison question instead.")

    tracer = Tracer()           # new tracer for each request
    start_time = time.time()

    tracer.log("received", f"Question: {request.question[:80]}")

    # Step 1: Planner decomposes question into axes and sub-queries
    tracer.log("planning", "Decomposing question into research axes and sub-queries")
    try:
        planner_output = await plan(request.question, tracer=tracer)
    except Exception as e:
        tracer.log("error", f"Planner failed: {str(e)[:200]}")   # after all retries fail
        # Return a generic message to the client. The full exception can contain
        # raw LLM output, provider error bodies, or internal paths - none of
        # which belong in an HTTP response body.
        raise HTTPException(status_code=502, detail="Planner failed. See server logs for details.")     # 502 = Bad Gateway
    tracer.log(
        "planned",
        f"{planner_output.technology_a} vs {planner_output.technology_b}, "
        f"{len(planner_output.axes)} axes, {len(planner_output.sub_queries)} sub-queries",
    )

    # Step 2: Searcher fetches evidence from Tavily for each sub-query
    tracer.log("searching", f"Running {len(planner_output.sub_queries)} Tavily searches")
    try:
        raw_results = await search(planner_output.sub_queries)
    except Exception as e:
        tracer.log("error", f"Searcher failed: {str(e)[:200]}")
        raise HTTPException(status_code=502, detail="Searcher failed. See server logs for details.")
    tracer.log("searched", f"Retrieved {len(raw_results)} raw results from Tavily")

    # Step 3: Cleaner deduplicates results and assigns trust tiers
    tracer.log("cleaning", "Deduplicating results and assigning trust tiers")
    cleaned = clean_and_deduplicate(raw_results)        # no await because this is synchronous (pure Python, no network calls)
    tracer.log("cleaned", f"{len(cleaned)} results after cleaning (from {len(raw_results)} raw)")

    if not cleaned:
        tracer.log("warning", "No sources survived cleaning. Matrix will have insufficient data.")

    # Step 4: Synthesizer builds the trade-off matrix via LLM
    tracer.log("synthesizing", "Building trade-off matrix with LLM")
    try:
        matrix = await synthesize_matrix(planner_output, cleaned, tracer=tracer)
    except Exception as e:
        tracer.log("error", f"Synthesizer failed: {str(e)[:200]}")
        raise HTTPException(status_code=502, detail="Synthesizer failed. See server logs for details.")
    tracer.log(
        "synthesized",
        f"{len(matrix.cells)} cells, {len(matrix.conflicts)} conflicts, "
        f"{len(matrix.insufficient_data)} insufficient axes",
    )

    # Step 5: Build final response with trace and latency
    latency = round(time.time() - start_time, 2)
    tracer.log("complete", f"Pipeline finished in {latency}s")
    logger.info("Pipeline complete in %.2fs: %d sources, %d cells", latency, len(cleaned), len(matrix.cells))

    # calculate token usage and estimated cost
    total_tokens = tracer.total_prompt_tokens + tracer.total_completion_tokens
    estimated_cost = (tracer.total_prompt_tokens * INPUT_COST_PER_M + tracer.total_completion_tokens * OUTPUT_COST_PER_M) / 1_000_000

    return AgentResponse(
        matrix=matrix,
        trace=tracer.get_steps(),
        total_sources=len(cleaned),
        latency_seconds=latency,
        token_usage=TokenUsage(
            prompt_tokens=tracer.total_prompt_tokens,
            completion_tokens=tracer.total_completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(estimated_cost, 6),
        ),
    )

@app.get("/api/research/stream")      # SSE streaming endpoint for live trace updates
async def research_stream(question: str = Query(..., min_length=10, max_length=500)):       # question as URL query parameter (SSE only supports GET)
    """Stream the research pipeline step by step using Server-Sent Events."""

    # Check for prompt injection before starting the stream
    injection = check_injection(question)
    if injection:
        logger.warning("Prompt injection blocked: %s (pattern: %s)", question[:80], injection)
        raise HTTPException(status_code=400, detail="Your query appears to contain instructions that conflict with the agent's purpose. Please ask a technology comparison question instead.")

    async def event_generator():
        tracer = Tracer()
        start_time = time.time()

        tracer.log("received", f"Question: {question[:80]}")

        # Step 1: Plan
        tracer.log("planning", "Decomposing question into research axes and sub-queries")
        yield format_sse({"step": "planning", "detail": "Decomposing question into research axes"})
        try:
            planner_output = await plan(question, tracer=tracer)
        except Exception as e:
            tracer.log("error", f"Planner failed: {str(e)[:200]}")
            yield format_sse({"step": "error", "detail": "Planner failed. See server logs for details."})
            return
        tracer.log(
            "planned",
            f"{planner_output.technology_a} vs {planner_output.technology_b}, "
            f"{len(planner_output.axes)} axes, {len(planner_output.sub_queries)} sub-queries",
        )
        yield format_sse({
            "step": "planned",
            "detail": f"{planner_output.technology_a} vs {planner_output.technology_b}, "
                      f"{len(planner_output.axes)} axes, {len(planner_output.sub_queries)} sub-queries",
        })

        # Step 2: Search
        tracer.log("searching", f"Running {len(planner_output.sub_queries)} Tavily searches")
        yield format_sse({"step": "searching", "detail": f"Running {len(planner_output.sub_queries)} Tavily searches"})
        try:
            raw_results = await search(planner_output.sub_queries)
        except Exception as e:
            tracer.log("error", f"Searcher failed: {str(e)[:200]}")
            yield format_sse({"step": "error", "detail": "Searcher failed. See server logs for details."})
            return
        tracer.log("searched", f"Retrieved {len(raw_results)} raw results from Tavily")
        yield format_sse({"step": "searched", "detail": f"Retrieved {len(raw_results)} raw results from Tavily"})

        # Step 3: Clean
        tracer.log("cleaning", "Deduplicating results and assigning trust tiers")
        yield format_sse({"step": "cleaning", "detail": "Deduplicating results and assigning trust tiers"})
        cleaned = clean_and_deduplicate(raw_results)
        tracer.log("cleaned", f"{len(cleaned)} results after cleaning (from {len(raw_results)} raw)")
        yield format_sse({"step": "cleaned", "detail": f"{len(cleaned)} results after cleaning (from {len(raw_results)} raw)"})

        # Step 4: Synthesize
        tracer.log("synthesizing", "Building trade-off matrix with LLM")
        yield format_sse({"step": "synthesizing", "detail": "Building trade-off matrix with LLM"})
        try:
            matrix = await synthesize_matrix(planner_output, cleaned, tracer=tracer)
        except Exception as e:
            tracer.log("error", f"Synthesizer failed: {str(e)[:200]}")
            yield format_sse({"step": "error", "detail": "Synthesizer failed. See server logs for details."})
            return
        tracer.log(
            "synthesized",
            f"{len(matrix.cells)} cells, {len(matrix.conflicts)} conflicts, "
            f"{len(matrix.insufficient_data)} insufficient axes",
        )

        # Step 5: Complete
        latency = round(time.time() - start_time, 2)
        tracer.log("complete", f"Pipeline finished in {latency}s")
        logger.info("Pipeline complete in %.2fs: %d sources, %d cells", latency, len(cleaned), len(matrix.cells))

        # calculate token usage and estimated cost
        total_tokens = tracer.total_prompt_tokens + tracer.total_completion_tokens
        estimated_cost = (tracer.total_prompt_tokens * INPUT_COST_PER_M + tracer.total_completion_tokens * OUTPUT_COST_PER_M) / 1_000_000

        response = AgentResponse(
            matrix=matrix,
            trace=tracer.get_steps(),
            total_sources=len(cleaned),
            latency_seconds=latency,
            token_usage=TokenUsage(      
                prompt_tokens=tracer.total_prompt_tokens,
                completion_tokens=tracer.total_completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=round(estimated_cost, 6),
            ),
        )
        yield format_sse({
            "step": "complete",
            "detail": f"Pipeline finished in {latency}s",
            "data": response.model_dump(),       # full response payload for the frontend to render (now includes token_usage automatically)
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",     # tells browser it is a stream of events not a normal JSON response
        headers={
            "Cache-Control": "no-cache",      # prevents browsers and proxies from caching the stream
            "Connection": "keep-alive",        # keeps the HTTP connection open for the duration of the stream
        },
    )