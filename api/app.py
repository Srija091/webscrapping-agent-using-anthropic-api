"""
CogniScan REST API
FastAPI application exposing the scan agent over HTTP.

Endpoints:
  GET  /                  → health check + available sources
  POST /scan              → run a full multi-source scan
  POST /summarise         → summarise a single article URL
  GET  /sources           → list available government sources
  GET  /suggested-queries → return suggested query list
"""

from __future__ import annotations

import logging
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.scanner import CogniScanAgent
from config import GOVERNMENT_SOURCES, SUGGESTED_QUERIES, settings
from models.schemas import (
    HealthResponse,
    ScanRequest,
    ScanResponse,
    SummariseRequest,
    SummariseResponse,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

app = FastAPI(
    title="CogniScan API",
    description=(
        "AI-powered agent that searches official government health news sites "
        "for cognitive and mental health articles and returns AI-generated summaries."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-init agent (validates API key on first use)
_agent: CogniScanAgent | None = None


def get_agent() -> CogniScanAgent:
    global _agent
    if _agent is None:
        _agent = CogniScanAgent()
    return _agent


# ---------------------------------------------------------------------------
# Exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Check API health and list available sources."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        available_sources=list(GOVERNMENT_SOURCES.keys()),
        suggested_queries=SUGGESTED_QUERIES,
    )


@app.get("/sources", tags=["Sources"])
async def list_sources() -> dict:
    """Return all available government health sources with metadata."""
    return {
        key: {
            "name": src.name,
            "base_url": src.base_url,
            "search_domain": src.search_domain,
            "description": src.description,
        }
        for key, src in GOVERNMENT_SOURCES.items()
    }


@app.get("/suggested-queries", tags=["Queries"])
async def suggested_queries() -> dict:
    """Return a list of suggested mental health search queries."""
    return {"queries": SUGGESTED_QUERIES}


@app.post("/scan", response_model=ScanResponse, tags=["Scan"])
async def scan(request: ScanRequest) -> ScanResponse:
    """
    Run a full scan across selected government health sources.

    - **query**: What to search for (e.g. "depression treatment guidelines")
    - **sources**: List of source keys to include (default: CDC, NIMH, SAMHSA, NIH, WHO, HHS)
    - **max_articles**: How many articles to return (1–15, default 6)
    """
    # Validate sources
    invalid = [s for s in request.sources if s not in GOVERNMENT_SOURCES]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown source(s): {invalid}. Valid keys: {list(GOVERNMENT_SOURCES.keys())}",
        )

    try:
        agent = get_agent()
        response = agent.scan(
            query=request.query,
            sources=request.sources,
            max_articles=request.max_articles,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/summarise", response_model=SummariseResponse, tags=["Summarise"])
async def summarise(request: SummariseRequest) -> SummariseResponse:
    """
    Fetch and summarise a single article from a government health URL.

    - **url**: Full URL of the article to summarise
    - **source**: Optional source hint (e.g. "CDC")
    """
    try:
        agent = get_agent()
        result = agent.summarise_url(url=request.url, source=request.source)
        return SummariseResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
