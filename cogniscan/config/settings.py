"""
CogniScan Configuration
Centralizes all settings, government source definitions, and topic keywords.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Government health sources
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GovSource:
    key: str
    name: str
    base_url: str
    search_domain: str          # used in site: search operators
    description: str
    color: str = "#00c8a0"


GOVERNMENT_SOURCES: dict[str, GovSource] = {
    "CDC": GovSource(
        key="CDC",
        name="Centers for Disease Control and Prevention",
        base_url="https://www.cdc.gov",
        search_domain="cdc.gov",
        description="National public health agency of the United States",
        color="#0077ff",
    ),
    "NIMH": GovSource(
        key="NIMH",
        name="National Institute of Mental Health",
        base_url="https://www.nimh.nih.gov",
        search_domain="nimh.nih.gov",
        description="Lead federal agency for mental health research",
        color="#a855f7",
    ),
    "SAMHSA": GovSource(
        key="SAMHSA",
        name="Substance Abuse and Mental Health Services Administration",
        base_url="https://www.samhsa.gov",
        search_domain="samhsa.gov",
        description="US agency leading public health efforts for behavioral health",
        color="#f59e0b",
    ),
    "NIH": GovSource(
        key="NIH",
        name="National Institutes of Health",
        base_url="https://www.nih.gov",
        search_domain="nih.gov",
        description="Primary US government biomedical research agency",
        color="#00c8a0",
    ),
    "WHO": GovSource(
        key="WHO",
        name="World Health Organization",
        base_url="https://www.who.int",
        search_domain="who.int",
        description="Global public health agency of the United Nations",
        color="#ff6b6b",
    ),
    "HHS": GovSource(
        key="HHS",
        name="US Department of Health & Human Services",
        base_url="https://www.hhs.gov",
        search_domain="hhs.gov",
        description="US federal department responsible for public health and welfare",
        color="#34d399",
    ),
    "VA": GovSource(
        key="VA",
        name="US Department of Veterans Affairs",
        base_url="https://www.mentalhealth.va.gov",
        search_domain="va.gov",
        description="Federal agency serving US military veterans",
        color="#a855f7",
    ),
    "HRSA": GovSource(
        key="HRSA",
        name="Health Resources & Services Administration",
        base_url="https://www.hrsa.gov",
        search_domain="hrsa.gov",
        description="US agency improving health care to people who are underserved",
        color="#34d399",
    ),
}

# Mental-health / cognition topic keywords (used to enrich search queries)
MENTAL_HEALTH_KEYWORDS: list[str] = [
    "mental health",
    "cognitive health",
    "depression",
    "anxiety",
    "PTSD",
    "schizophrenia",
    "bipolar disorder",
    "ADHD",
    "autism spectrum",
    "dementia",
    "Alzheimer's",
    "cognitive decline",
    "behavioral health",
    "substance use disorder",
    "addiction",
    "suicide prevention",
    "eating disorders",
    "OCD",
    "psychosis",
    "neurodevelopmental",
]

SUGGESTED_QUERIES: list[str] = [
    "depression and anxiety treatment guidelines",
    "cognitive decline prevention in adults",
    "PTSD research and therapy updates",
    "children and adolescent mental health",
    "substance use disorder and mental health co-occurrence",
    "mindfulness and behavioral therapy outcomes",
    "suicide prevention strategies",
    "dementia and Alzheimer's research",
    "ADHD in adults evidence-based treatment",
    "maternal mental health postpartum",
]


# ---------------------------------------------------------------------------
# App settings (read from env with safe defaults)
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = "claude-sonnet-4-20250514"
    max_articles: int = int(os.getenv("MAX_ARTICLES", "6"))
    summary_max_tokens: int = int(os.getenv("SUMMARY_MAX_TOKENS", "1500"))
    search_timeout: int = int(os.getenv("SEARCH_TIMEOUT", "30"))
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    default_sources: list[str] = field(
        default_factory=lambda: ["CDC", "NIMH", "SAMHSA", "NIH", "WHO", "HHS"]
    )

    def validate(self) -> None:
        if not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.example → .env and add your key."
            )


settings = Settings()
