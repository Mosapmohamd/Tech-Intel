# Tech Intelligence Agent — Project Specification

> This is the authoritative specification. Build strictly against it.

## Role

Senior AI Engineer, Python Architect, and Software Designer building a
production-ready personal AI Technical Intelligence Agent.

This is **not** a news scraper. It is an AI-powered weekly technical
intelligence assistant that helps a software engineer stay current with
important technology developments.

The project must be clean, modular, maintainable, extensible, and follow
software engineering best practices.

## Objective

A Python application that automatically:

1. Collects technology news every day
2. Extracts full article content
3. Removes duplicates
4. Filters unreliable sources
5. Categorizes articles
6. Scores each article
7. Summarizes each article in Arabic
8. Generates technical insights
9. Stores everything in a local database
10. Generates a weekly report every Sunday at 09:00 local time
11. Sends the report by email

The system must be completely free to operate apart from the local machine.
All AI tasks run on a local Ollama instance.

## Tech Stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.12+ |
| Package manager | uv |
| Environment | `.env` |
| Database | SQLite |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Scheduler | APScheduler |
| LLM | Ollama |
| Web extraction | trafilatura |
| RSS parsing | feedparser |
| Templates | Jinja2 |
| Email | SMTP |
| Logging | loguru |
| CLI | Typer |
| Configuration | pydantic-settings |
| Testing | pytest |
| Lint | Ruff |
| Formatting | Black |
| Type checking | mypy |

## Architecture

Clean Architecture. Target structure:

```
project/
  app/
    core/
      config/
      database/
      models/
      repositories/
      services/
    agents/
      collector/
        rss/
      extractor/
      classifier/
      ranker/
      summarizer/
      insight/
      report/
      email/
      scheduler/
    templates/
    prompts/
    utils/
  tests/
  docs/
  scripts/
  main.py
  README.md
  pyproject.toml
  .env.example
```

## AI Agents

Implement the system as multiple specialized agents. **Every agent has exactly
one responsibility.**

| Agent | Responsibility |
| --- | --- |
| Collector | Collect RSS feeds |
| Extractor | Extract the full readable article |
| Cleaning | Normalize text |
| Deduplication | Remove duplicated news |
| Classification | Assign categories |
| Ranking | Calculate the importance score |
| Summary | Generate the Arabic summary |
| Insight | Explain why the news matters |
| Report | Generate the weekly digest |
| Email | Send the email |
| Scheduler | Run jobs automatically |

## RSS Sources

New feeds must be addable from a configuration file **without changing code**.

- **General** — TechCrunch, The Verge, Ars Technica, Wired
- **AI** — OpenAI Blog, Anthropic, Google AI, Meta AI, Hugging Face
- **Programming** — GitHub Blog, Microsoft DevBlogs, JetBrains
- **Cloud** — AWS Blog, Azure Blog, Google Cloud Blog, Docker Blog, Kubernetes Blog
- **Security** — Cloudflare, Cisco Talos, Microsoft Security, KrebsOnSecurity
- **Database** — MongoDB Blog, PostgreSQL Blog, Redis Blog
- **Open Source** — Linux Foundation, Apache Foundation

## Workflow

**Daily**

```
Collect RSS → Extract article → Clean text → Remove duplicates →
Categorize → Rank → Summarize → Generate insight → Store in SQLite
```

**Weekly**

```
Load all articles → Rank → Select Top 10 → Select Worth Watching (3) →
Generate executive summary → Generate trends → Generate recommendations →
Generate HTML email → Send email
```

## Categories

AI, Programming, Cybersecurity, Cloud, DevOps, Open Source, Databases,
Web Development, Mobile, Hardware, Big Tech, Startups, Research, Crypto, Other

## Scoring

Build a scoring engine producing a final score from 0–100.

| Component | Weight |
| --- | --- |
| Source quality | 30% |
| Recency | 20% |
| Cross-source mentions | 15% |
| Technical impact | 20% |
| LLM importance | 15% |

**Store every component of the score**, not just the total.

## Ollama

- Default model: `qwen3:14b`
- The model name must be configurable
- Every AI task uses a prompt template
- **Never hardcode prompts**

## AI Tasks

For every article, generate:

- Arabic title
- Arabic summary (maximum 120 words)
- Key points
- Why it matters
- Who should care
- Technical impact
- Recommended action
- Confidence score

## Weekly Report

- **Executive Summary**
- **Top 10 Stories** — each with title, source, date, Arabic summary,
  why it matters, link, category, and importance score
- **Worth Watching** — 3 additional stories
- **Technology Trends** — categories ranked by activity
- **Professional Picks** — advanced news for experienced engineers
- **AI Recommendations** — written specifically for software engineers

## Email

Version 1: simple HTML, responsive, readable in Gmail, dark-mode friendly,
no external CSS.

## Database

Tables for: Sources, Articles, Categories, Summaries, Insights, Scores,
Weekly Reports, Email History, Jobs.

- Do not duplicate articles
- Track whether an article has already been included in a report

## Configuration

Everything must be configurable; **never hardcode values**:
RSS sources, email settings, schedule, LLM model, database path,
maximum articles, maximum summary length, categories, scoring weights.

## Security

Use environment variables. Never store credentials in source code.
Provide `.env.example`.

## Logging

Log every pipeline step. Support DEBUG, INFO, WARNING, ERROR.
Rotate logs automatically.

## Error Handling

- Retry failed RSS downloads
- Skip broken articles
- Continue the pipeline if one source fails
- Log all failures

## CLI

Commands: `collect`, `summarize`, `report`, `send`, `schedule`, `test-email`,
`rebuild-db`, `add-source`, `list-sources`, `stats`.

## Documentation

A professional README covering installation, configuration, running,
scheduling, project structure, environment variables, troubleshooting,
and future improvements.

## Code Quality

- Follow SOLID principles
- Use dependency injection where appropriate
- Every module has docstrings
- Every public function has type hints
- Avoid duplicated code
- Keep functions small

## Future Extensibility

Design so these can be added without major refactoring: Telegram, Discord,
Slack, and Microsoft Teams notifications; web dashboard; FastAPI REST API;
authentication; user profiles; personalized recommendations; vector database;
semantic search; daily digest; monthly reports; podcast generation; voice
summaries; mobile app.

## Delivery Phases

Generate the project incrementally. **Do not skip phases.**

| Phase | Deliverable |
| --- | --- |
| 1 | Create project structure |
| 2 | Implement database |
| 3 | Implement RSS collectors |
| 4 | Implement extraction |
| 5 | Implement deduplication |
| 6 | Implement scoring |
| 7 | Implement Ollama integration |
| 8 | Generate reports |
| 9 | Generate HTML email |
| 10 | Scheduler |
| 11 | Testing |
| 12 | Documentation |

At the end of each phase:

- Explain design decisions
- Show the directory tree
- Show modified files
- Explain how to test the phase
- **Wait for approval before starting the next phase**
