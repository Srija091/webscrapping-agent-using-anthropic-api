"""
CogniScan Data Models
Pydantic v2 schemas for requests, responses, and internal structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


# ---------------------------------------------------------------------------
# Article model (core output unit)
# ---------------------------------------------------------------------------

class Article(BaseModel):
    title: str = Field(..., description="Full title of the article")
    source: str = Field(..., description="Source key e.g. CDC, NIMH")
    source_name: Optional[str] = Field(None, description="Full source name")
    url: str = Field(..., description="URL of the original article")
    date: Optional[str] = Field(None, description="Publication date string")
    topics: list[str] = Field(default_factory=list, description="Topic/keyword tags")
    relevance: float = Field(0.8, ge=0.0, le=1.0, description="Relevance score 0-1")
    summary: str = Field(..., description="AI-generated summary")
    key_findings: list[str] = Field(default_factory=list, description="Key extracted findings")
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("relevance", mode="before")
    @classmethod
    def clamp_relevance(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @field_validator("topics", "key_findings", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v or []


# ---------------------------------------------------------------------------
# Scan request / response
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Search query about mental health topics")
    sources: list[str] = Field(
        default=["CDC", "NIMH", "SAMHSA", "NIH", "WHO", "HHS"],
        description="List of source keys to search",
    )
    max_articles: int = Field(default=6, ge=1, le=15)

    @field_validator("sources", mode="before")
    @classmethod
    def uppercase_sources(cls, v: list[str]) -> list[str]:
        return [s.upper() for s in v]


class ScanResponse(BaseModel):
    query: str
    query_interpreted: str
    sources_searched: list[str]
    total_found: int
    articles: list[Article]
    scan_duration_seconds: float
    scanned_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Summarise single article request
# ---------------------------------------------------------------------------

class SummariseRequest(BaseModel):
    url: str = Field(..., description="URL of an article to summarise")
    source: Optional[str] = Field(None, description="Source hint e.g. CDC")


class SummariseResponse(BaseModel):
    url: str
    title: str
    summary: str
    key_findings: list[str]
    topics: list[str]
    source: Optional[str] = None


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    available_sources: list[str]
    suggested_queries: list[str]
