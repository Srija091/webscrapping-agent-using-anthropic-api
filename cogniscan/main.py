#!/usr/bin/env python3
"""
CogniScan CLI
A rich terminal interface for the government mental health news agent.

Usage examples:
  python main.py scan "depression treatment"
  python main.py scan "PTSD" --sources CDC NIMH VA
  python main.py scan "anxiety" --export report.md
  python main.py summarise https://www.nimh.nih.gov/...
  python main.py sources
  python main.py serve
"""

from __future__ import annotations

import sys
import os
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Prompt

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from agent.scanner import CogniScanAgent
from config import GOVERNMENT_SOURCES, SUGGESTED_QUERIES, settings
from models.schemas import ScanRequest, SummariseRequest
from utils.formatting import (
    console,
    print_banner,
    print_scan_response,
    print_sources_table,
    format_export,
)

logging.basicConfig(level=logging.WARNING)  # suppress info noise in CLI

app_cli = typer.Typer(
    name="cogniscan",
    help="🧠 CogniScan — Government Mental Health News Agent",
    add_completion=False,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# scan command
# ---------------------------------------------------------------------------

@app_cli.command()
def scan(
    query: str = typer.Argument(..., help="What to search for, e.g. 'PTSD treatment'"),
    sources: Optional[list[str]] = typer.Option(
        None, "--sources", "-s",
        help="Source keys to search (default: all 6 main sources). "
             "E.g. --sources CDC --sources NIMH",
    ),
    max_articles: int = typer.Option(6, "--max", "-n", help="Max articles to return (1–15)"),
    export: Optional[Path] = typer.Option(
        None, "--export", "-e",
        help="Export results to a Markdown file",
    ),
) -> None:
    """
    [bold cyan]Scan[/bold cyan] government health sources for mental health articles.
    """
    print_banner()

    selected_sources = sources or settings.default_sources
    invalid = [s.upper() for s in selected_sources if s.upper() not in GOVERNMENT_SOURCES]
    if invalid:
        console.print(f"[red]Unknown source(s): {invalid}[/red]")
        console.print(f"Valid options: {list(GOVERNMENT_SOURCES.keys())}")
        raise typer.Exit(1)

    selected_sources = [s.upper() for s in selected_sources]

    console.print(
        f"[dim]Scanning:[/dim] [cyan]{', '.join(selected_sources)}[/cyan]  "
        f"[dim]for:[/dim] [italic]{query}[/italic]"
    )
    console.print()

    with console.status("[cyan]Agent working — searching government health sources…[/cyan]"):
        try:
            agent = CogniScanAgent()
            response = agent.scan(
                query=query,
                sources=selected_sources,
                max_articles=max(1, min(15, max_articles)),
            )
        except ValueError as e:
            console.print(f"[red]Configuration error:[/red] {e}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Agent error:[/red] {e}")
            raise typer.Exit(1)

    print_scan_response(response)

    if export:
        md_content = format_export(response)
        export.write_text(md_content, encoding="utf-8")
        console.print(f"\n[green]✓ Report saved to:[/green] {export}")


# ---------------------------------------------------------------------------
# summarise command
# ---------------------------------------------------------------------------

@app_cli.command()
def summarise(
    url: str = typer.Argument(..., help="URL of a government health article to summarise"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source key hint e.g. CDC"),
) -> None:
    """
    [bold cyan]Summarise[/bold cyan] a single government health article by URL.
    """
    print_banner()
    console.print(f"[dim]Summarising:[/dim] {url}\n")

    with console.status("[cyan]Fetching and summarising article…[/cyan]"):
        try:
            agent = CogniScanAgent()
            result = agent.summarise_url(url=url, source=source)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    from rich.panel import Panel
    lines = [
        f"[bold]{result.get('title', 'Unknown title')}[/bold]",
        "",
        result.get("summary", "No summary available."),
    ]
    findings = result.get("key_findings", [])
    if findings:
        lines += ["", "[bold]Key Findings:[/bold]"]
        for f in findings:
            lines.append(f"  [cyan]→[/cyan] {f}")
    topics = result.get("topics", [])
    if topics:
        lines.append("")
        lines.append("  ".join(f"[dim]#{t}[/dim]" for t in topics))
    lines += ["", f"[dim]🔗 {url}[/dim]"]

    console.print(Panel("\n".join(lines), border_style="cyan", padding=(0, 1)))


# ---------------------------------------------------------------------------
# sources command
# ---------------------------------------------------------------------------

@app_cli.command()
def sources() -> None:
    """
    [bold cyan]List[/bold cyan] all available government health sources.
    """
    print_banner()
    print_sources_table(GOVERNMENT_SOURCES)


# ---------------------------------------------------------------------------
# queries command
# ---------------------------------------------------------------------------

@app_cli.command()
def queries() -> None:
    """
    [bold cyan]Show[/bold cyan] suggested mental health search queries.
    """
    print_banner()
    console.print("\n[bold]Suggested Queries:[/bold]\n")
    for i, q in enumerate(SUGGESTED_QUERIES, 1):
        console.print(f"  [cyan]{i:2}.[/cyan]  {q}")
    console.print()


# ---------------------------------------------------------------------------
# interactive command
# ---------------------------------------------------------------------------

@app_cli.command()
def interactive() -> None:
    """
    [bold cyan]Interactive[/bold cyan] REPL — scan repeatedly without restarting.
    """
    print_banner()
    console.print(
        "[dim]Type a query and press Enter to scan. "
        "Type [bold]quit[/bold] or [bold]exit[/bold] to stop.[/dim]\n"
    )

    agent = CogniScanAgent()

    while True:
        try:
            query = Prompt.ask("[cyan]Query[/cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if query.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break
        if not query:
            continue

        with console.status("[cyan]Scanning…[/cyan]"):
            try:
                response = agent.scan(query=query, sources=settings.default_sources)
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}\n")
                continue

        print_scan_response(response)


# ---------------------------------------------------------------------------
# serve command
# ---------------------------------------------------------------------------

@app_cli.command()
def serve(
    host: str = typer.Option(settings.api_host, "--host", "-H"),
    port: int = typer.Option(settings.api_port, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)"),
) -> None:
    """
    [bold cyan]Serve[/bold cyan] the CogniScan REST API with Uvicorn.
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is not installed.[/red] Run: pip install uvicorn")
        raise typer.Exit(1)

    print_banner()
    console.print(f"[green]Starting API server[/green] → http://{host}:{port}")
    console.print(f"[dim]Docs: http://{host}:{port}/docs[/dim]\n")

    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app_cli()
