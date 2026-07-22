"""Tests for the Cleaning Agent and the Extractor Agent."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.agents.extractor import ExtractorAgent
from app.agents.extractor.cleaner import clean_text, count_words
from app.core.config import Settings
from app.core.database.base import utcnow
from app.core.models import Article, ArticleStatus, JobStatus, Source
from app.core.repositories import ArticleRepository, JobRepository, SourceRepository
from app.utils.hashing import content_hash, url_hash

LONG_ARTICLE_HTML = """<html><head><title>Rust 2.0 released</title></head><body>
<nav>Home About Contact</nav>
<article>
<h1>Rust 2.0 released</h1>
<p>The Rust project announced today the release of Rust 2.0, a major milestone
for the systems programming language that has been in development for the
past three years. This release brings a significant number of improvements
to the compiler, the standard library, and the tooling ecosystem that
surrounds the language.</p>
<p>According to the release notes, the new version focuses heavily on
compile time performance, reducing average build times by roughly forty
percent across a wide sample of real world crates. The team also rewrote
large parts of the borrow checker to produce clearer error messages for
beginners and experienced developers alike.</p>
<p>In addition to performance work, Rust 2.0 introduces a handful of new
syntax features that were stabilized after going through the RFC process for
several years. These include improvements to async syntax, better support
for const generics, and a simplified module system that many developers
have been requesting since the language reached 1.0.</p>
<p>The community has responded positively to the announcement, with package
maintainers already beginning to test their crates against the new compiler
in preparation for a broader ecosystem migration over the coming months.</p>
</article>
<footer>Copyright 2026</footer>
</body></html>"""

SHORT_ARTICLE_HTML = """<html><head><title>Quick note</title></head><body>
<article><h1>Quick note</h1><p>Just a short update, nothing more to say here.</p></article>
</body></html>"""

NO_CONTENT_HTML = "<html><head><title>Empty</title></head><body></body></html>"


class StubDownloader:
    """An ArticleDownloader stand-in returning scripted responses."""

    def __init__(self, responses: dict[str, str | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []
        self.closed = False

    def fetch(self, url: str) -> str:
        self.calls.append(url)
        outcome = self.responses[url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        self.closed = True


def _make_source(db: Session, slug: str = "alpha") -> Source:
    return SourceRepository(db).upsert(
        slug=slug, name="Alpha Blog", feed_url=f"https://{slug}.example.com/feed"
    )


def _make_article(
    db: Session, source: Source, url: str, *, title: str = "Rust 2.0 released"
) -> Article:
    return ArticleRepository(db).add(
        Article(
            source_id=source.id,
            url=url,
            url_hash=url_hash(url),
            title=title,
            published_at=datetime(2026, 7, 14, tzinfo=UTC),
            collected_at=utcnow(),
            status=ArticleStatus.COLLECTED,
        )
    )


class TestCleaner:
    def test_normalizes_whitespace_and_blank_lines(self) -> None:
        raw = "Title\n\n\n\nBody line with trailing space \nMore text\x0c"
        cleaned = clean_text(raw)
        assert "\n\n\n" not in cleaned
        assert cleaned == cleaned.strip()

    def test_count_words(self) -> None:
        assert count_words("one two three") == 3
        assert count_words("") == 0


class TestExtractorAgent:
    def _agent(self, db: Session, settings: Settings, downloader: StubDownloader) -> ExtractorAgent:
        return ExtractorAgent(db, settings=settings, downloader=downloader)  # type: ignore[arg-type]

    def test_successful_extraction_stores_content_and_hash(
        self, db: Session, settings: Settings
    ) -> None:
        source = _make_source(db)
        article = _make_article(db, source, "https://alpha.example.com/rust-2")
        downloader = StubDownloader({article.url: LONG_ARTICLE_HTML})

        result = self._agent(db, settings, downloader).extract()

        assert result.extracted == 1
        assert result.failed == 0
        assert result.skipped == 0
        stored = ArticleRepository(db).get(article.id)
        assert stored is not None
        assert stored.status == ArticleStatus.EXTRACTED
        assert stored.content is not None
        assert stored.word_count > 100
        assert stored.extracted_at is not None
        assert stored.content_hash == content_hash(stored.title, stored.content)

    def test_download_failure_marks_article_failed_and_continues(
        self, db: Session, settings: Settings
    ) -> None:
        source = _make_source(db)
        broken = _make_article(db, source, "https://alpha.example.com/broken")
        healthy = _make_article(db, source, "https://alpha.example.com/rust-2")
        downloader = StubDownloader(
            {broken.url: ConnectionError("DNS failure"), healthy.url: LONG_ARTICLE_HTML}
        )

        result = self._agent(db, settings, downloader).extract()

        assert result.failed == 1
        assert result.extracted == 1
        stored_broken = ArticleRepository(db).get(broken.id)
        assert stored_broken is not None
        assert stored_broken.status == ArticleStatus.FAILED
        assert "DNS failure" in (stored_broken.error_message or "")

    def test_short_content_is_skipped(self, db: Session, settings: Settings) -> None:
        source = _make_source(db)
        article = _make_article(db, source, "https://alpha.example.com/short", title="Quick note")
        downloader = StubDownloader({article.url: SHORT_ARTICLE_HTML})

        result = self._agent(db, settings, downloader).extract()

        assert result.skipped == 1
        assert result.extracted == 0
        stored = ArticleRepository(db).get(article.id)
        assert stored is not None
        assert stored.status == ArticleStatus.SKIPPED
        assert stored.content is None
        assert "too short" in (stored.error_message or "")

    def test_no_extractable_content_marks_failed(self, db: Session, settings: Settings) -> None:
        source = _make_source(db)
        article = _make_article(db, source, "https://alpha.example.com/empty")
        downloader = StubDownloader({article.url: NO_CONTENT_HTML})

        result = self._agent(db, settings, downloader).extract()

        assert result.failed == 1
        stored = ArticleRepository(db).get(article.id)
        assert stored is not None
        assert stored.status == ArticleStatus.FAILED
        assert stored.error_message == "No extractable content found"

    def test_limit_is_respected(self, db: Session, settings: Settings) -> None:
        source = _make_source(db)
        first = _make_article(db, source, "https://alpha.example.com/a")
        second = _make_article(db, source, "https://alpha.example.com/b")
        downloader = StubDownloader({first.url: LONG_ARTICLE_HTML, second.url: LONG_ARTICLE_HTML})

        result = self._agent(db, settings, downloader).extract(limit=1)

        assert result.processed == 1
        assert len(downloader.calls) == 1

    def test_job_run_is_recorded(self, db: Session, settings: Settings) -> None:
        source = _make_source(db)
        article = _make_article(db, source, "https://alpha.example.com/rust-2")
        downloader = StubDownloader({article.url: LONG_ARTICLE_HTML})

        self._agent(db, settings, downloader).extract()

        job = JobRepository(db).list_recent(1)[0]
        assert job.name == "extract"
        assert job.status == JobStatus.SUCCESS
        assert job.items_processed == 1

    def test_partial_failure_marks_job_partial(self, db: Session, settings: Settings) -> None:
        source = _make_source(db)
        broken = _make_article(db, source, "https://alpha.example.com/broken")
        healthy = _make_article(db, source, "https://alpha.example.com/rust-2")
        downloader = StubDownloader(
            {broken.url: ConnectionError("boom"), healthy.url: LONG_ARTICLE_HTML}
        )

        self._agent(db, settings, downloader).extract()

        job = JobRepository(db).list_recent(1)[0]
        assert job.status == JobStatus.PARTIAL

    def test_only_collected_articles_are_processed(self, db: Session, settings: Settings) -> None:
        source = _make_source(db)
        already_extracted = _make_article(db, source, "https://alpha.example.com/done")
        already_extracted.status = ArticleStatus.EXTRACTED
        downloader = StubDownloader({})

        result = self._agent(db, settings, downloader).extract()

        assert result.processed == 0
        assert downloader.calls == []
