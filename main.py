"""Tech Intelligence Agent — CLI entry point.

Commands are registered here in Phase 1 as stubs and wired to real
implementations in later phases. Run ``python main.py --help`` to list them.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="tia",
    help="Personal AI Technical Intelligence Agent.",
    no_args_is_help=True,
)

_NOT_IMPLEMENTED = "Not implemented yet — arrives in phase {phase}."


def _todo(phase: int) -> None:
    """Print a friendly placeholder until the owning phase lands."""
    typer.secho(_NOT_IMPLEMENTED.format(phase=phase), fg=typer.colors.YELLOW)


@app.command()
def collect() -> None:
    """Run the daily collection pipeline (RSS → extract → store)."""
    _todo(phase=3)


@app.command()
def summarize() -> None:
    """Summarize and analyze pending articles with the local LLM."""
    _todo(phase=7)


@app.command()
def report() -> None:
    """Generate the weekly report from stored articles."""
    _todo(phase=8)


@app.command()
def send() -> None:
    """Send the latest weekly report by email."""
    _todo(phase=9)


@app.command()
def schedule() -> None:
    """Start the scheduler (daily collect + weekly report)."""
    _todo(phase=10)


@app.command("test-email")
def test_email() -> None:
    """Send a test email to verify SMTP configuration."""
    _todo(phase=9)


@app.command("rebuild-db")
def rebuild_db() -> None:
    """Drop and recreate all database tables."""
    _todo(phase=2)


@app.command("add-source")
def add_source() -> None:
    """Register a new RSS source."""
    _todo(phase=3)


@app.command("list-sources")
def list_sources() -> None:
    """List all configured RSS sources."""
    _todo(phase=3)


@app.command()
def stats() -> None:
    """Show database and pipeline statistics."""
    _todo(phase=2)


if __name__ == "__main__":
    app()
