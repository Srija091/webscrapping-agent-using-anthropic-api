"""
CogniScan Core Agent
Orchestrates web search via the Anthropic API (claude + web_search tool),
parses the structured JSON results, and returns validated Article objects.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

import anthropic

from config import settings, GOVERNMENT_SOURCES, MENTAL_HEALTH_KEYWORDS
from models.schemas import Article, ScanResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """You are CogniScan, a specialist government health news intelligence agent.
Your role is to find, analyse, and summarise recent articles related to cognitive and mental health
published on official government health websites.

BEHAVIOUR:
1. Use the web_search tool to query the user's specified government sources.
2. Search with targeted queries combining the user's topic with the source domains.
3. Retrieve and analyse article content to produce accurate summaries.
4. Return ONLY a valid JSON object — no markdown fences, no preamble, no explanation.

OUTPUT FORMAT (strict JSON, no extra text):
{
  "articles": [
    {
      "title": "Full article title",
      "source": "SOURCE_KEY (CDC|NIMH|SAMHSA|NIH|WHO|HHS|VA|HRSA)",
      "url": "https://...",
      "date": "Month YYYY or YYYY-MM-DD",
      "topics": ["tag1", "tag2", "tag3"],
      "relevance": 0.95,
      "summary": "2–3 sentence factual summary of the article's main content and findings.",
      "key_findings": [
        "Specific finding or statistic from the article.",
        "Another concrete takeaway.",
        "A third important point."
      ]
    }
  ],
  "total_searched": 6,
  "query_interpreted": "Brief description of how the query was interpreted"
}

RULES:
- Return 3–6 articles. Prioritise recency and relevance to mental/cognitive health.
- Each article must genuinely address cognitive or mental health topics.
- relevance must be a float between 0.0 and 1.0.
- key_findings must contain 2–4 specific, factual bullet points extracted from the article.
- If a source has no relevant articles, skip it rather than inventing content.
- Never fabricate URLs — only return URLs confirmed by search results.
"""


def _build_user_prompt(query: str, sources: list[str], max_articles: int) -> str:
    source_lines = []
    for key in sources:
        src = GOVERNMENT_SOURCES.get(key)
        if src:
            source_lines.append(f"  - {key}: {src.name} ({src.search_domain})")

    keyword_hint = ", ".join(MENTAL_HEALTH_KEYWORDS[:8])

    return f"""Search for recent articles about: "{query}"

Search these government health sources:
{chr(10).join(source_lines)}

Guidelines:
- Use site: operators to restrict results to the domains listed above.
- Combine the user's query with mental health keywords such as: {keyword_hint}
- Try multiple searches if needed to find {max_articles} relevant articles.
- Prioritise articles published in the last 2 years where possible.
- Extract real titles, real URLs, and factual summaries from the search results.

Return exactly the JSON structure specified in your instructions."""


# ---------------------------------------------------------------------------
# Main agent class
# ---------------------------------------------------------------------------

class CogniScanAgent:
    """
    Wraps the Anthropic client and orchestrates:
      1. Building a targeted search prompt for the specified sources.
      2. Calling claude-sonnet with the web_search tool enabled.
      3. Parsing + validating the structured JSON response.
      4. Returning a ScanResponse with validated Article objects.
    """

    def __init__(self) -> None:
        settings.validate()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        max_articles: int = 6,
    ) -> ScanResponse:
        """
        Synchronous scan. Calls the Anthropic API and returns a ScanResponse.
        Raises on API errors; returns partial results on JSON parse failures.
        """
        sources = sources or settings.default_sources
        sources = [s.upper() for s in sources if s.upper() in GOVERNMENT_SOURCES]

        if not sources:
            raise ValueError("No valid sources specified. Choose from: " + ", ".join(GOVERNMENT_SOURCES))

        logger.info("Starting scan | query=%r | sources=%s", query, sources)
        t0 = time.perf_counter()

        raw = self._call_api(query, sources, max_articles)
        parsed = self._parse_response(raw)

        articles = self._build_articles(parsed.get("articles", []))
        duration = time.perf_counter() - t0

        logger.info("Scan complete | %d articles | %.2fs", len(articles), duration)

        return ScanResponse(
            query=query,
            query_interpreted=parsed.get("query_interpreted", query),
            sources_searched=sources,
            total_found=len(articles),
            articles=articles,
            scan_duration_seconds=round(duration, 2),
        )

    def summarise_url(self, url: str, source: Optional[str] = None) -> dict:
        """
        Fetch and summarise a single article URL using the Anthropic API.
        Returns a dict matching SummariseResponse fields.
        """
        prompt = (
            f"Fetch and summarise this government health article: {url}\n\n"
            "Return ONLY this JSON (no markdown):\n"
            "{\n"
            '  "title": "...",\n'
            '  "summary": "2-3 sentence summary",\n'
            '  "key_findings": ["finding1", "finding2", "finding3"],\n'
            '  "topics": ["tag1", "tag2", "tag3"]\n'
            "}"
        )
        msg = self.client.messages.create(
            model=settings.model,
            max_tokens=800,
            system=(
                "You are a precise health article summariser. "
                "Use web_search to fetch the article, then return ONLY valid JSON."
            ),
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = self._extract_text(msg.content)
        data = self._safe_parse_json(text)
        data["url"] = url
        data["source"] = source
        return data

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_api(self, query: str, sources: list[str], max_articles: int) -> list:
        """Call the Anthropic messages API with web_search enabled."""
        user_prompt = _build_user_prompt(query, sources, max_articles)

        message = self.client.messages.create(
            model=settings.model,
            max_tokens=settings.summary_max_tokens,
            system=AGENT_SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content

    def _extract_text(self, content_blocks: list) -> str:
        """Concatenate all text blocks from a response."""
        return "\n".join(
            b.text for b in content_blocks if hasattr(b, "text") and b.text
        )

    def _parse_response(self, content_blocks: list) -> dict:
        text = self._extract_text(content_blocks)
        return self._safe_parse_json(text)

    def _safe_parse_json(self, text: str) -> dict:
        """Strip markdown fences, find the outermost JSON object, parse it."""
        # Remove ```json ... ``` fences
        text = re.sub(r"```(?:json)?", "", text).strip()

        # Find outermost braces
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("No JSON object found in response; returning empty.")
            return {"articles": [], "query_interpreted": "", "total_searched": 0}

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s\nRaw text: %.500s", e, text)
            return {"articles": [], "query_interpreted": "", "total_searched": 0}

    def _build_articles(self, raw_articles: list[dict]) -> list[Article]:
        """Validate and construct Article objects, skipping bad entries."""
        articles = []
        for raw in raw_articles:
            try:
                # Enrich with full source name if available
                source_key = str(raw.get("source", "")).upper()
                src_obj = GOVERNMENT_SOURCES.get(source_key)
                if src_obj:
                    raw["source"] = source_key
                    raw["source_name"] = src_obj.name

                article = Article(**raw)
                articles.append(article)
            except Exception as e:
                logger.warning("Skipping invalid article: %s | raw=%s", e, raw)
        return articles
