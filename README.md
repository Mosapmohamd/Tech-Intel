# Tech Intelligence Agent

Personal AI Technical Intelligence Agent — collects technology news daily,
analyzes it with a local LLM (Ollama), and emails a curated weekly digest
with Arabic summaries every Sunday at 09:00.

> **Status:** under incremental construction (Phase 1 of 12 — project structure).
> Full documentation lands in Phase 12.

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
