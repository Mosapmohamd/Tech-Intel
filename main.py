"""Tech Intelligence Agent — CLI entry point.

Commands are registered here in Phase 1 as stubs and wired to real
implementations in later phases. Run ``python main.py --help`` to list them.
"""

from __future__ import annotations

import json

import typer

from app.core.config import SourceConfig
from app.core.services import (
    add_source as add_source_service,
)
from app.core.services import (
    bootstrap_database,
    check_feeds,
    collect_stats,
    run_collection,
    run_extraction,
    sync_sources,
)
from app.core.services import (
    list_sources as list_sources_service,
)
from app.utils.logging import setup_logging

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
def collect(
    source: str | None = typer.Option(None, "--source", "-s", help="Collect one source only."),
) -> None:
    """Collect new entries from every active RSS source."""
    setup_logging()
    result = run_collection(only=source)
    typer.secho(
        f"\nNew articles: {result.new_articles}  |  "
        f"already stored: {result.duplicates}  |  "
        f"unchanged feeds: {result.sources_unchanged}  |  "
        f"failed: {result.sources_failed}/{result.sources_total}",
        fg=typer.colors.GREEN if result.sources_failed == 0 else typer.colors.YELLOW,
    )
    for outcome in result.per_source:
        if not outcome.ok:
            typer.secho(f"  ✗ {outcome.slug}: {outcome.error}", fg=typer.colors.RED)


@app.command("check-feeds")
def check_feeds_command(
    source: str | None = typer.Option(None, "--source", "-s", help="Check one source only."),
) -> None:
    """Probe every feed and report which ones are reachable and parseable."""
    setup_logging()
    results = check_feeds(only=source)
    failures = [r for r in results if not r.ok]

    typer.secho(f"\n{'SLUG':<22}RESULT", bold=True)
    for result in results:
        typer.secho(
            f"{result.slug:<22}{result.summary}",
            fg=typer.colors.RED if not result.ok else None,
        )
    colour = typer.colors.GREEN if not failures else typer.colors.YELLOW
    typer.secho(f"\n{len(results) - len(failures)}/{len(results)} feeds healthy.\n", fg=colour)
    if failures:
        raise typer.Exit(code=1)


@app.command()
def extract(
    limit: int | None = typer.Option(
        None, "--limit", "-l", help="Max number of articles to process."
    ),
) -> None:
    """Extract full article content for collected articles."""
    setup_logging()
    result = run_extraction(limit=limit)
    typer.secho(
        f"\nExtracted: {result.extracted}  |  skipped: {result.skipped}  |  "
        f"failed: {result.failed}  |  processed: {result.processed}",
        fg=typer.colors.GREEN if result.failed == 0 else typer.colors.YELLOW,
    )
    for failure in result.failures:
        typer.secho(
            f"  ✗ [{failure.article_id}] {failure.url}: {failure.error}", fg=typer.colors.RED
        )


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
def rebuild_db(
    force: bool = typer.Option(False, "--force", help="Skip the confirmation prompt."),
    keep_data: bool = typer.Option(
        False, "--keep-data", help="Create missing tables only; do not drop existing ones."
    ),
) -> None:
    """Create the database schema, optionally dropping existing tables first."""
    setup_logging()
    if not keep_data and not force:
        typer.confirm("This deletes ALL stored articles and reports. Continue?", abort=True)
    result = bootstrap_database(rebuild=not keep_data)
    typer.secho(
        f"Database ready. Categories seeded: {result['categories_created']}",
        fg=typer.colors.GREEN,
    )


@app.command("add-source")
def add_source(
    slug: str = typer.Option(..., help="Unique stable id, e.g. 'my-blog'."),
    name: str = typer.Option(..., help="Display name."),
    feed_url: str = typer.Option(..., help="RSS or Atom feed URL."),
    group: str = typer.Option("general", help="Catalogue group."),
    site_url: str | None = typer.Option(None, help="Homepage URL."),
    category: str | None = typer.Option(None, "--category", help="Default category slug."),
    quality: float = typer.Option(0.7, min=0.0, max=1.0, help="Source quality weight."),
) -> None:
    """Register a new RSS source in sources.yaml and the database."""
    setup_logging()
    try:
        config = SourceConfig(
            slug=slug,
            name=name,
            feed_url=feed_url,
            site_url=site_url,
            group=group,
            default_category=category,
            quality_weight=quality,
        )
        add_source_service(config)
    except (ValueError, FileNotFoundError) as exc:
        typer.secho(f"Could not add source: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(f"Added {slug} to group '{group}'.", fg=typer.colors.GREEN)


@app.command("list-sources")
def list_sources(
    sync: bool = typer.Option(False, "--sync", help="Reload sources.yaml into the database first."),
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON."),
) -> None:
    """List all configured RSS sources with their health status."""
    setup_logging()
    if sync:
        sync_sources()
    rows = list_sources_service()
    if as_json:
        typer.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        typer.secho(
            "No sources yet. Run 'list-sources --sync' to load sources.yaml.",
            fg=typer.colors.YELLOW,
        )
        return

    typer.secho(f"\n{'SLUG':<22}{'GROUP':<14}{'W':<6}{'OK':<4}{'FAIL':<6}LAST SUCCESS", bold=True)
    for row in rows:
        mark = "✓" if row["is_active"] else "–"
        colour = typer.colors.RED if row["failures"] else None
        typer.secho(
            f"{row['slug']:<22}{row['group']:<14}{row['quality_weight']:<6.2f}"
            f"{mark:<4}{row['failures']:<6}{row['last_success_at'] or 'never'}",
            fg=colour,
        )
    typer.echo(f"\n{len(rows)} source(s).\n")


@app.command()
def stats(
    as_json: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a table.")
) -> None:
    """Show database and pipeline statistics."""
    setup_logging()
    data = collect_stats()
    if as_json:
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    typer.secho("\nTech Intelligence Agent — statistics", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  Database        : {data['database']}")
    typer.echo(
        f"  Sources         : {data['sources_active']} active / {data['sources_total']} total"
    )
    typer.echo(f"  Articles        : {data['articles_total']}")
    for status, count in sorted(data["articles_by_status"].items()):
        typer.echo(f"      {status:<12}: {count}")
    typer.echo(f"  Weekly reports  : {data['reports_total']}")
    typer.echo(f"  Emails sent     : {data['emails_total']}")
    typer.echo(f"  Job runs        : {data['jobs_total']}")
    for job in data["recent_jobs"]:
        typer.echo(f"      {job['started_at']}  {job['name']:<16} {job['status']}")
    typer.echo("")


if __name__ == "__main__":
    app()
