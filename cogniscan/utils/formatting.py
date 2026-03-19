"""
CogniScan Utilities — formatting helpers for CLI output.
"""

from __future__ import annotations

from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from models.schemas import Article, ScanResponse

console = Console()


def print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]🧠  CogniScan[/bold cyan]  "
            "[dim]— Government Mental Health News Agent[/dim]",
            border_style="cyan",
        )
    )


def print_scan_response(response: ScanResponse) -> None:
    """Pretty-print a full scan response to the terminal."""
    console.print()
    console.print(
        f"[bold]Query:[/bold] [italic]{response.query}[/italic]   "
        f"[dim]({response.total_found} articles · "
        f"{response.scan_duration_seconds:.1f}s)[/dim]"
    )
    console.print(
        f"[dim]Interpreted as:[/dim] [italic]{response.query_interpreted}[/italic]"
    )
    console.print(
        f"[dim]Sources searched:[/dim] {', '.join(response.sources_searched)}"
    )
    console.print()

    for i, article in enumerate(response.articles, 1):
        _print_article(article, index=i)


def _print_article(article: Article, index: int = 1) -> None:
    relevance_bar = _make_bar(article.relevance)
    source_color = {
        "CDC": "blue", "NIMH": "magenta", "SAMHSA": "yellow",
        "NIH": "cyan", "WHO": "red", "HHS": "green",
        "VA": "magenta", "HRSA": "green",
    }.get(article.source, "white")

    header = (
        f"[{source_color}][{article.source}][/{source_color}]  "
        f"[bold]{article.title}[/bold]"
    )

    body_lines = [
        f"[dim]📅  {article.date or 'Date unknown'}   "
        f"🎯 Relevance: {relevance_bar} {int(article.relevance * 100)}%[/dim]",
        "",
        f"[italic]{article.summary}[/italic]",
    ]

    if article.key_findings:
        body_lines.append("")
        body_lines.append("[bold]Key Findings:[/bold]")
        for finding in article.key_findings:
            body_lines.append(f"  [cyan]→[/cyan] {finding}")

    if article.topics:
        body_lines.append("")
        tags = "  ".join(f"[dim]#{t}[/dim]" for t in article.topics)
        body_lines.append(tags)

    body_lines.append("")
    body_lines.append(f"[link={article.url}][dim]🔗 {article.url}[/dim][/link]")

    console.print(
        Panel(
            "\n".join(body_lines),
            title=header,
            title_align="left",
            border_style="dim",
            padding=(0, 1),
        )
    )


def _make_bar(value: float, width: int = 10) -> str:
    filled = round(value * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[cyan]{bar}[/cyan]"


def print_sources_table(sources: dict) -> None:
    table = Table(title="Available Government Sources", box=box.ROUNDED, border_style="cyan")
    table.add_column("Key", style="bold cyan", width=8)
    table.add_column("Name", style="white")
    table.add_column("Domain", style="dim")
    table.add_column("Description", style="dim")
    for key, src in sources.items():
        table.add_row(key, src.name, src.search_domain, src.description)
    console.print(table)


def format_export(response: ScanResponse) -> str:
    """Return a plain-text markdown report of the scan results."""
    lines = [
        f"# CogniScan Report",
        f"**Query:** {response.query}",
        f"**Interpreted as:** {response.query_interpreted}",
        f"**Sources:** {', '.join(response.sources_searched)}",
        f"**Articles found:** {response.total_found}",
        f"**Scanned at:** {response.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
    ]
    for i, a in enumerate(response.articles, 1):
        lines += [
            f"## {i}. {a.title}",
            f"- **Source:** {a.source_name or a.source}",
            f"- **Date:** {a.date or 'Unknown'}",
            f"- **Relevance:** {int(a.relevance * 100)}%",
            f"- **URL:** {a.url}",
            "",
            f"**Summary:** {a.summary}",
            "",
        ]
        if a.key_findings:
            lines.append("**Key Findings:**")
            for f in a.key_findings:
                lines.append(f"- {f}")
            lines.append("")
        if a.topics:
            lines.append(f"**Topics:** {', '.join(a.topics)}")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)
