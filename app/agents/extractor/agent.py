"""Extractor Agent — fills in the full article body for collected entries.

Single responsibility: turn a ``COLLECTED`` article into an ``EXTRACTED`` one
by downloading its page and pulling out the readable text. It does not decide
what counts as a duplicate (Deduplication Agent, phase 5) and it does not
touch SQLAlchemy directly — all persistence goes through the repositories.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.extractor.cleaner import clean_text, count_words
from app.agents.extractor.content import extract_content
from app.agents.extractor.downloader import ArticleDownloader
from app.core.config import Settings, get_settings
from app.core.database.base import utcnow
from app.core.models import Article, ArticleStatus, JobStatus
from app.core.repositories import ArticleRepository, JobRepository
from app.utils.hashing import content_hash


@dataclass(slots=True)
class ArticleFailure:
    """A single article that could not be extracted or was skipped."""

    article_id: int
    url: str
    error: str


@dataclass(slots=True)
class ExtractionResult:
    """Aggregate outcome of an extraction run."""

    processed: int = 0
    extracted: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[ArticleFailure] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serializable summary, stored on the JobRun record."""
        return {
            "processed": self.processed,
            "extracted": self.extracted,
            "skipped": self.skipped,
            "failed": self.failed,
            "failures": [asdict(f) for f in self.failures],
        }


class ExtractorAgent:
    """Downloads and extracts full-text content for collected articles.

    The HTTP downloader is injected so the agent can be exercised in tests
    with a stub in place of real network calls.
    """

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        downloader: ArticleDownloader | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session
        self.articles = ArticleRepository(session)
        self.jobs = JobRepository(session)
        self._downloader = downloader
        self._owns_downloader = downloader is None

    def extract(self, *, limit: int | None = None, trigger: str = "manual") -> ExtractionResult:
        """Run a full extraction pass over articles awaiting content.

        A failing article is logged and recorded, never fatal — one broken
        page must not cost us the rest of the batch.

        Args:
            limit: Maximum number of articles to process. Defaults to
                ``settings.extraction_batch_size``.
            trigger: Recorded on the JobRun ("manual" or "cron").
        """
        job = self.jobs.start("extract", trigger=trigger)
        result = ExtractionResult()
        downloader = self._downloader or ArticleDownloader(
            timeout=float(self.settings.extraction_timeout_seconds),
            attempts=self.settings.extraction_attempts,
        )

        try:
            batch_size = limit if limit is not None else self.settings.extraction_batch_size
            queue = self.articles.list_by_status(ArticleStatus.COLLECTED, limit=batch_size)
            result.processed = len(queue)

            for article in queue:
                self._extract_one(article, downloader, result)

            status = self._job_status(result)
            self.jobs.finish(
                job,
                status=status,
                processed=result.extracted,
                failed=result.failed,
                details=result.as_dict(),
            )
            logger.info(
                "Extraction finished: {} extracted, {} skipped, {} failed (of {})",
                result.extracted,
                result.skipped,
                result.failed,
                result.processed,
            )
            return result
        except Exception as exc:
            self.jobs.finish(job, status=JobStatus.FAILED, error=str(exc))
            raise
        finally:
            if self._owns_downloader:
                downloader.close()

    # ── internals ────────────────────────────────────────────

    @staticmethod
    def _job_status(result: ExtractionResult) -> JobStatus:
        """Map an extraction outcome onto a job status."""
        if result.failed == 0:
            return JobStatus.SUCCESS
        if result.failed < result.processed:
            return JobStatus.PARTIAL
        return JobStatus.FAILED

    def _extract_one(
        self, article: Article, downloader: ArticleDownloader, result: ExtractionResult
    ) -> None:
        """Extract one article, isolating any failure from the rest of the batch."""
        try:
            html = downloader.fetch(article.url)
            text = extract_content(html, url=article.url)
            if text is None:
                self._mark_failed(article, "No extractable content found", result)
                return

            cleaned = clean_text(text)
            word_count = count_words(cleaned)
            if word_count < self.settings.min_extracted_words:
                self._mark_skipped(article, word_count, result)
                return

            article.content = cleaned
            article.word_count = word_count
            article.content_hash = content_hash(article.title, cleaned)
            article.extracted_at = utcnow()
            article.status = ArticleStatus.EXTRACTED
            self.session.flush()
            result.extracted += 1
            logger.debug("Extracted article {} ({} words)", article.id, word_count)
        except Exception as exc:  # noqa: BLE001 — one bad article must not stop the batch
            self._mark_failed(article, str(exc), result)

    def _mark_failed(self, article: Article, error: str, result: ExtractionResult) -> None:
        article.status = ArticleStatus.FAILED
        article.error_message = error
        self.session.flush()
        result.failed += 1
        result.failures.append(ArticleFailure(article_id=article.id, url=article.url, error=error))
        logger.warning("Article {} failed extraction: {}", article.id, error)

    def _mark_skipped(self, article: Article, word_count: int, result: ExtractionResult) -> None:
        message = f"Content too short ({word_count} words)"
        article.status = ArticleStatus.SKIPPED
        article.error_message = message
        self.session.flush()
        result.skipped += 1
        logger.debug("Article {} skipped: {}", article.id, message)
