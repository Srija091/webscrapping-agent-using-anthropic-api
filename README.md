# 🧠 CogniScan — Government Mental Health News Agent

An AI-powered Python agent that searches official government health websites for articles on cognitive and mental health, and returns structured AI-generated summaries.

---

## Features

- **Multi-source scanning** across CDC, NIMH, SAMHSA, NIH, WHO, HHS, VA, HRSA
- **AI-powered summaries** with key findings extraction (Claude + web_search tool)
- **REST API** (FastAPI) for integration into web apps or dashboards
- **Rich CLI** with interactive REPL, export to Markdown, and table views
- **Validated schemas** via Pydantic v2
- **Full test suite** (pytest)

---

## Project Structure

```
cogniscan/
├── main.py               # CLI entrypoint (Typer)
├── requirements.txt
├── .env.example
│
├── agent/
│   └── scanner.py        # Core AI agent (Anthropic API + web_search)
│
├── api/
│   └── app.py            # FastAPI REST application
│
├── config/
│   └── settings.py       # Settings, source definitions, keywords
│
├── models/
│   └── schemas.py        # Pydantic v2 request/response models
│
├── utils/
│   ├── scraper.py        # HTTP fetcher + HTML parser (BeautifulSoup)
│   └── formatting.py     # Rich terminal formatting helpers
│
└── tests/
    └── test_cogniscan.py # Full pytest test suite
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your API key

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run the CLI

```bash
# Basic scan
python main.py scan "depression treatment guidelines"

# Specify sources
python main.py scan "PTSD" --sources CDC --sources NIMH --sources VA

# Limit results and export to Markdown
python main.py scan "cognitive decline" --max 4 --export report.md

# Summarise a single article
python main.py summarise https://www.nimh.nih.gov/health/topics/depression

# Interactive REPL
python main.py interactive

# List all available sources
python main.py sources

# Show suggested queries
python main.py queries
```

### 4. Start the REST API

```bash
python main.py serve
# → http://localhost:8000
# → Docs: http://localhost:8000/docs
```

---

## REST API

| Method | Endpoint            | Description                          |
|--------|---------------------|--------------------------------------|
| GET    | `/`                 | Health check + available sources     |
| GET    | `/sources`          | List government sources with metadata|
| GET    | `/suggested-queries`| Suggested search queries             |
| POST   | `/scan`             | Run a full multi-source scan         |
| POST   | `/summarise`        | Summarise a single article URL       |

### POST /scan — Request body

```json
{
  "query": "depression and anxiety treatment guidelines",
  "sources": ["CDC", "NIMH", "SAMHSA"],
  "max_articles": 6
}
```

### POST /scan — Response

```json
{
  "query": "depression and anxiety treatment guidelines",
  "query_interpreted": "Evidence-based treatment for depression and anxiety",
  "sources_searched": ["CDC", "NIMH", "SAMHSA"],
  "total_found": 4,
  "articles": [
    {
      "title": "Depression — National Institute of Mental Health",
      "source": "NIMH",
      "source_name": "National Institute of Mental Health",
      "url": "https://www.nimh.nih.gov/health/topics/depression",
      "date": "2024-03",
      "topics": ["depression", "treatment", "antidepressants"],
      "relevance": 0.97,
      "summary": "Overview of depression symptoms, causes, and evidence-based treatment options including psychotherapy and medication.",
      "key_findings": [
        "Depression affects over 21 million adults in the US each year.",
        "Cognitive behavioral therapy (CBT) is recommended as first-line treatment.",
        "Combination of therapy and medication is most effective for moderate-severe depression."
      ]
    }
  ],
  "scan_duration_seconds": 8.4,
  "scanned_at": "2025-04-01T14:22:10"
}
```

---

## Configuration

All settings can be overridden via `.env`:

| Variable             | Default               | Description                        |
|----------------------|-----------------------|------------------------------------|
| `ANTHROPIC_API_KEY`  | (required)            | Your Anthropic API key             |
| `MAX_ARTICLES`       | `6`                   | Default max articles per scan      |
| `SUMMARY_MAX_TOKENS` | `1500`                | Token budget for summaries         |
| `SEARCH_TIMEOUT`     | `30`                  | HTTP timeout in seconds            |
| `API_HOST`           | `0.0.0.0`             | API bind host                      |
| `API_PORT`           | `8000`                | API port                           |

---

## Available Sources

| Key     | Name                                           | Domain        |
|---------|------------------------------------------------|---------------|
| CDC     | Centers for Disease Control and Prevention     | cdc.gov       |
| NIMH    | National Institute of Mental Health            | nimh.nih.gov  |
| SAMHSA  | Substance Abuse and Mental Health Services     | samhsa.gov    |
| NIH     | National Institutes of Health                  | nih.gov       |
| WHO     | World Health Organization                      | who.int       |
| HHS     | US Dept of Health & Human Services             | hhs.gov       |
| VA      | US Dept of Veterans Affairs                    | va.gov        |
| HRSA    | Health Resources & Services Administration     | hrsa.gov      |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## How It Works

1. **CLI / API** receives a query + source selection
2. `CogniScanAgent.scan()` builds a targeted prompt with `site:` operators for each source
3. The Anthropic API (Claude Sonnet) runs with `web_search` tool enabled — it autonomously searches, retrieves articles, and summarises them
4. The structured JSON response is parsed, validated with Pydantic, and returned
5. CLI renders results with Rich; API returns JSON

---

## Disclaimer

This tool provides research assistance by summarising publicly available government health information. Always verify content at the original source before clinical or policy use. Not a substitute for professional medical advice.
