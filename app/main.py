import logging
import time
from contextlib import asynccontextmanager      # creates startup/shutdown hooks for FastAPI
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware      # for deployment
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import AgentResponse, QueryRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health() -> dict[str, str]:       # Health check endpoint for deployment platforms
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root() -> FileResponse:       # Serve the main web UI (index.html)
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not built yet")
    return FileResponse(str(index_path))


@app.post("/api/research", response_model=AgentResponse)
async def research(request: QueryRequest) -> AgentResponse:     # Run the full research agent pipeline
    logger.info("Research request received: %s", request.question[:80])
    start_time = time.time()

    # TODO: Wire up the four-step agent pipeline
    # Step 1: planner.plan(request.question)
    # Step 2: searcher.search(planner_output.sub_queries)
    # Step 3: cleaner.clean(search_results)
    # Step 4: synthesizer.synthesize(cleaned_results)

    latency = time.time() - start_time
    logger.info("Pipeline not yet implemented. Latency so far: %.2fs", latency)

    raise HTTPException(
        status_code=501,
        detail="Agent pipeline not yet wired. Build steps 1 through 4 first.",
    )