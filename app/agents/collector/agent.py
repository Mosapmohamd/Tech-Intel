"""Collector Agent — the single responsibility is getting feed entries into the database.

It does not extract article bodies (Extractor Agent, phase 4) and it does not
decide what is a duplicate beyond the cheap exact-URL check needed to avoid
re-inserting the same row (Deduplication Agent, phase 5).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.collector.rss.client import FeedClient
from app.agents.collector.rss.parser import FeedItem, parse_feed
from app.core.config import Settings, get_settings
from app.core.config.loader import SourceCatalogue, load_sources
from app.core.database.base import utcnow
from app.core.models import Article, ArticleStatus, JobStatus, Source
from app.core.repositories import ArticleRepository, JobRepository, SourceRepository


@dataclass(slots=True)
class SourceResult:
    """Per-source outcome of a collection run."""

    slug: str
    fetched: int = 0
    new: int = 0
    duplicates: int = 0
    not_modified: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Whether this source completed without error."""
        return self.error is None


@dataclass(slots=True)
class CollectionResult:
    """Aggregate outcome of a collection run."""

    sources_total: int = 0
    sources_failed: int = 0
    sources_unchanged: int = 0
    new_articles: int = 0
    duplicates: int = 0
    per_source: list[SourceResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serializable summary, stored on the JobRun record."""
        return {
            "sources_total": self.sources_total,
            "sources_failed": self.sources_failed,
            "sources_unchanged": self.sources_unchanged,
            "new_articles": self.new_articles,
            "duplicates": self.duplicates,
            "per_source": [asdict(result) for result in self.per_source],
        }


class CollectorAgent:
    """Fetches every active source and stores newly seen entries.

    Dependencies are injected so the agent can be exercised in tests with a
    stub client and an in-memory database.
    """

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        client: FeedClient | None = None,
        catalogue: SourceCatalogue | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session
        self.sources = SourceRepository(session)
        self.articles = ArticleRepository(session)
        self.jobs = JobRepository(session)
        self._catalogue = catalogue
        self._client = client
        self._owns_client = client is None

    # ── catalogue ────────────────────────────────────────────

    def sync_catalogue(self) -> int:
        """Reconcile ``sources.yaml`` into the ``sources`` table.

        Returns:
            The number of sources present after syncing.
        """
        catalogue = self._catalogue or load_sources(settings=self.settings)
        for config in catalogue.sources:
            self.sources.upsert(**config.to_orm_fields())
        logger.info("Source catalogue synced ({} sources)", len(catalogue.sources))
        return len(catalogue.sources)

    # ── collection ───────────────────────────────────────────

    def collect(self, *, only: str | None = None, trigger: str = "manual") -> CollectionResult:
        """Run a full collection pass over the active sources.

        A failing source is logged and recorded, never fatal — one dead feed
        must not cost us the other twenty-five.

        Args:
            only: Restrict the run to a single source slug.
            trigger: Recorded on the JobRun ("manual" or "cron").
        """
        job = self.jobs.start("collect", trigger=trigger)
        result = CollectionResult()
        client = self._client or FeedClient(timeout=float(self.settings.ollama_timeout_seconds))

        try:
            targets = self._select_sources(only)
            result.sources_total = len(targets)

            for source in targets:
                outcome = self._collect_source(source, client)
                result.per_source.append(outcome)
                result.new_articles += outcome.new
                result.duplicates += outcome.duplicates
                result.sources_failed += 0 if outcome.ok else 1
                result.sources_unchanged += 1 if outcome.not_modified else 0

            status = self._job_status(result)
            self.jobs.finish(
                job,
                status=status,
                processed=result.new_articles,
                failed=result.sources_failed,
                details=result.as_dict(),
            )
            logger.info(
                "Collection finished: {} new, {} duplicates, {} unchanged, {} failed",
                result.new_articles,
                result.duplicates,
                result.sources_unchanged,
                result.sources_failed,
            )
            return result
        except Exception as exc:
            self.jobs.finish(job, status=JobStatus.FAILED, error=str(exc))
            raise
        finally:
            if self._owns_client:
                client.close()

    # ── internals ────────────────────────────────────────────

    def _select_sources(self, only: str | None) -> list[Source]:
        """Resolve which sources this run should touch."""
        if only is None:
            return list(self.sources.list_active())
        source = self.sources.get_by_slug(only)
        if source is None:
            raise ValueError(f"Unknown source slug: {only!r}")
        return [source]

    @staticmethod
    def _job_status(result: CollectionResult) -> JobStatus:
        """Map a collection outcome onto a job status."""
        if result.sources_failed == 0:
            return JobStatus.SUCCESS
        if result.sources_failed < result.sources_total:
            return JobStatus.PARTIAL
        return JobStatus.FAILED

    def _collect_source(self, source: Source, client: FeedClient) -> SourceResult:
        """Fetch, parse, and persist one source, isolating any failure."""
        outcome = SourceResult(slug=source.slug)
        try:
            response = client.fetch(
                source.feed_url, etag=source.etag, last_modified=source.last_modified
            )
        except Exception as exc:
            self.sources.mark_failure(source, str(exc))
            outcome.error = str(exc)
            logger.error("Source {} failed: {}", source.slug, exc)
            return outcome

        if response.not_modified:
            self.sources.mark_success(source)
            outcome.not_modified = True
            logger.debug("Source {} unchanged (HTTP 304)", source.slug)
            return outcome

        parsed = parse_feed(response.body, source_slug=source.slug)
        limit = self.settings.max_articles_per_source
        for item in parsed.items[:limit]:
            outcome.fetched += 1
            if self.articles.exists_url_hash(item.url_hash):
                outcome.duplicates += 1
                continue
            self.articles.add(self._to_article(source, item))
            outcome.new += 1

        source.etag = response.etag
        source.last_modified = response.last_modified
        self.sources.mark_success(source)
        logger.info(
            "Source {}: {} new / {} seen ({} already stored)",
            source.slug,
            outcome.new,
            outcome.fetched,
            outcome.duplicates,
        )
        return outcome

    @staticmethod
    def _to_article(source: Source, item: FeedItem) -> Article:
        """Map a normalized feed item onto a new Article row."""
        return Article(
            source_id=source.id,
            url=item.url,
            url_hash=item.url_hash,
            title=item.title,
            author=item.author,
            feed_summary=item.summary,
            published_at=item.published_at or utcnow(),
            collected_at=utcnow(),
            language=source.language,
            status=ArticleStatus.COLLECTED,
        )
