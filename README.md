# Tech Intelligence Agent

Personal AI Technical Intelligence Agent — collects technology news daily,
analyzes it with a local LLM (Ollama), and emails a curated weekly digest
with Arabic summaries every Sunday at 09:00.

> **Status:** under incremental construction. Phases 1–4 of 12 are complete (project
> structure, database layer, RSS collection, content extraction). Full documentation
> lands in Phase 12.

## Implemented so far

| Command | What it does |
|---|---|
| `python main.py collect [-s SOURCE]` | Fetch RSS feeds from the source catalogue and store new articles |
| `python main.py check-feeds [-s SOURCE]` | Health-check every feed URL (non-zero exit code if any fail) |
| `python main.py extract [--limit N]` | Download and clean full article text (trafilatura) |
| `python main.py list-sources` / `add-source` | Inspect or extend the source catalogue |
| `python main.py stats [--json]` | Database statistics |
| `python main.py rebuild-db` | Recreate the SQLite schema |

`summarize` (Phase 7), `report` (Phase 8), `send` / `test-email` (Phase 9) and `schedule` (Phase 10) are registered in the CLI but print a "not implemented yet" notice.

## Quick start (current phase)

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
python main.py --help
```

## Project structure

```
app/
  core/          # config, database, models, repositories, services
  agents/        # single-responsibility agents (collector, extractor, ...)
  templates/     # Jinja2 email/report templates
  prompts/       # LLM prompt templates (never hardcoded)
  utils/         # shared helpers
tests/           # pytest suite (unit + integration)
docs/            # documentation
scripts/         # operational scripts
data/            # SQLite database (gitignored)
logs/            # rotating logs (gitignored)
main.py          # Typer CLI entry point
```
