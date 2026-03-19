"""
CogniScan Test Suite
Covers config, models, scraper utilities, agent JSON parsing, and API routes.
Run with: pytest tests/ -v
"""

from __future__ import annotations

import json
import sys
import os
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_government_sources_loaded(self):
        from config import GOVERNMENT_SOURCES
        assert "CDC" in GOVERNMENT_SOURCES
        assert "NIMH" in GOVERNMENT_SOURCES
        assert "WHO" in GOVERNMENT_SOURCES

    def test_source_has_required_fields(self):
        from config import GOVERNMENT_SOURCES
        for key, src in GOVERNMENT_SOURCES.items():
            assert src.key == key
            assert src.search_domain
            assert src.base_url.startswith("http")

    def test_settings_defaults(self):
        from config import settings
        assert settings.max_articles > 0
        assert settings.model.startswith("claude")

    def test_settings_validate_raises_without_key(self, monkeypatch):
        from config import Settings
        s = Settings(anthropic_api_key="")
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            s.validate()


# ---------------------------------------------------------------------------
# Model / schema tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_article_valid(self):
        from models.schemas import Article
        a = Article(
            title="Test Article",
            source="CDC",
            url="https://cdc.gov/test",
            summary="A test summary.",
        )
        assert a.title == "Test Article"
        assert a.relevance == 0.8  # default

    def test_article_relevance_clamped(self):
        from models.schemas import Article
        a = Article(
            title="T", source="NIMH", url="https://nimh.nih.gov/x", summary="S",
            relevance=1.5,
        )
        assert a.relevance == 1.0

        b = Article(
            title="T", source="NIMH", url="https://nimh.nih.gov/y", summary="S",
            relevance=-0.5,
        )
        assert b.relevance == 0.0

    def test_article_topics_string_coercion(self):
        from models.schemas import Article
        a = Article(
            title="T", source="CDC", url="https://cdc.gov/t", summary="S",
            topics="mental health",
        )
        assert isinstance(a.topics, list)
        assert a.topics == ["mental health"]

    def test_scan_request_uppercase_sources(self):
        from models.schemas import ScanRequest
        req = ScanRequest(query="anxiety", sources=["cdc", "nimh"])
        assert req.sources == ["CDC", "NIMH"]

    def test_scan_response_structure(self):
        from models.schemas import ScanResponse, Article
        from datetime import datetime
        resp = ScanResponse(
            query="test",
            query_interpreted="test query",
            sources_searched=["CDC"],
            total_found=1,
            articles=[
                Article(title="A", source="CDC", url="https://cdc.gov", summary="S")
            ],
            scan_duration_seconds=1.23,
        )
        assert resp.total_found == 1
        assert isinstance(resp.scanned_at, datetime)


# ---------------------------------------------------------------------------
# Scraper utility tests
# ---------------------------------------------------------------------------

class TestScraper:
    def test_clean_text_collapses_whitespace(self):
        from utils.scraper import _clean_text
        messy = "\n\n  Hello  \n\n  World  \n"
        result = _clean_text(messy)
        assert "Hello" in result
        assert "World" in result

    def test_extract_article_text_minimal_html(self):
        from utils.scraper import extract_article_text
        html = """
        <html><head><title>Test Page</title>
        <meta name="description" content="A test article about mental health.">
        </head><body><main><p>Mental health is important.</p></main></body></html>
        """
        result = extract_article_text(html, url="https://cdc.gov/test")
        assert result["title"] == "Test Page"
        assert "mental health" in result["body"].lower()
        assert result["description"] == "A test article about mental health."

    def test_extract_article_strips_scripts(self):
        from utils.scraper import extract_article_text
        html = """
        <html><body>
        <script>alert('xss')</script>
        <main><p>Real content here.</p></main>
        </body></html>
        """
        result = extract_article_text(html)
        assert "alert" not in result["body"]
        assert "Real content here" in result["body"]

    def test_extract_date_from_meta(self):
        from utils.scraper import _extract_date
        from bs4 import BeautifulSoup
        html = '<html><head><meta property="article:published_time" content="2024-06-15T12:00:00Z"></head></html>'
        soup = BeautifulSoup(html, "lxml")
        date = _extract_date(soup)
        assert date == "2024-06-15"


# ---------------------------------------------------------------------------
# Agent JSON parsing tests (no API calls)
# ---------------------------------------------------------------------------

class TestAgentParsing:
    def _make_agent_no_validate(self):
        """Create agent instance bypassing API key validation for unit tests."""
        import unittest.mock as mock
        with mock.patch("config.settings.validate"):
            with mock.patch("anthropic.Anthropic"):
                from agent.scanner import CogniScanAgent
                agent = CogniScanAgent.__new__(CogniScanAgent)
                agent.client = mock.MagicMock()
                return agent

    def test_safe_parse_json_clean(self):
        from agent.scanner import CogniScanAgent
        agent = self._make_agent_no_validate()
        raw = '{"articles": [], "query_interpreted": "test", "total_searched": 0}'
        result = agent._safe_parse_json(raw)
        assert result["articles"] == []

    def test_safe_parse_json_strips_fences(self):
        from agent.scanner import CogniScanAgent
        agent = self._make_agent_no_validate()
        raw = '```json\n{"articles": [], "query_interpreted": "x"}\n```'
        result = agent._safe_parse_json(raw)
        assert isinstance(result, dict)

    def test_safe_parse_json_returns_empty_on_invalid(self):
        from agent.scanner import CogniScanAgent
        agent = self._make_agent_no_validate()
        result = agent._safe_parse_json("This is not JSON at all")
        assert result == {"articles": [], "query_interpreted": "", "total_searched": 0}

    def test_build_articles_filters_invalid(self):
        from agent.scanner import CogniScanAgent
        agent = self._make_agent_no_validate()
        raw = [
            # valid
            {"title": "Good", "source": "CDC", "url": "https://cdc.gov", "summary": "S"},
            # missing required fields — should be skipped
            {"source": "NIMH"},
        ]
        articles = agent._build_articles(raw)
        assert len(articles) == 1
        assert articles[0].source == "CDC"

    def test_build_articles_enriches_source_name(self):
        from agent.scanner import CogniScanAgent
        agent = self._make_agent_no_validate()
        raw = [{"title": "X", "source": "nimh", "url": "https://nimh.nih.gov", "summary": "S"}]
        articles = agent._build_articles(raw)
        assert articles[0].source == "NIMH"
        assert "National Institute" in articles[0].source_name


# ---------------------------------------------------------------------------
# API route tests (uses FastAPI TestClient)
# ---------------------------------------------------------------------------

class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        import unittest.mock as mock
        # Patch agent so no real API calls are made
        with mock.patch("api.app.get_agent") as mock_get:
            from models.schemas import ScanResponse, Article, SummariseResponse
            from datetime import datetime
            mock_agent = mock.MagicMock()
            mock_agent.scan.return_value = ScanResponse(
                query="depression",
                query_interpreted="depression treatment",
                sources_searched=["CDC"],
                total_found=1,
                articles=[
                    Article(
                        title="Depression Guide",
                        source="CDC",
                        url="https://cdc.gov/depression",
                        summary="A summary.",
                    )
                ],
                scan_duration_seconds=0.5,
            )
            mock_agent.summarise_url.return_value = {
                "title": "Test", "summary": "Sum", "key_findings": [],
                "topics": [], "url": "https://cdc.gov/x", "source": "CDC",
            }
            mock_get.return_value = mock_agent
            from api.app import app
            with TestClient(app) as c:
                yield c

    def test_health_check(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "CDC" in data["available_sources"]

    def test_sources_endpoint(self, client):
        resp = client.get("/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "CDC" in data
        assert "search_domain" in data["CDC"]

    def test_suggested_queries(self, client):
        resp = client.get("/suggested-queries")
        assert resp.status_code == 200
        assert "queries" in resp.json()

    def test_scan_endpoint(self, client):
        resp = client.post("/scan", json={"query": "depression", "sources": ["CDC"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_found"] == 1
        assert data["articles"][0]["title"] == "Depression Guide"

    def test_scan_invalid_source(self, client):
        resp = client.post("/scan", json={"query": "test", "sources": ["FAKESOURCE"]})
        assert resp.status_code == 422

    def test_summarise_endpoint(self, client):
        resp = client.post("/summarise", json={"url": "https://cdc.gov/x", "source": "CDC"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test"
