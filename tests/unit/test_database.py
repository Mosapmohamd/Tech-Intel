"""Tests for the database layer: schema, constraints, and repositories."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_engine, utcnow
from app.core.models import Article, ArticleStatus, Score, Source, Summary
from app.core.repositories import (
    ArticleRepository,
    CategoryRepository,
    JobRepository,
    ScoreRepository,
    SourceRepository,
)

EXPECTED_TABLES = {
    "sources",
    "articles",
    "categories",
    "article_categories",
    "summaries",
    "insights",
    "scores",
    "weekly_reports",
    "report_articles",
    "email_history",
    "jobs",
}


def _make_source(db: Session, slug: str = "techcrunch") -> Source:
    return SourceRepository(db).upsert(
        slug=slug,
        name=slug.title(),
        feed_url=f"https://{slug}.com/feed",
        group="general",
        quality_weight=0.9,
    )


def _make_article(
    db: Session, source: Source, *, url_hash: str, title: str = "Some news"
) -> Article:
    return ArticleRepository(db).add(
        Article(
            source_id=source.id,
            url=f"https://example.com/{url_hash}",
            url_hash=url_hash,
            title=title,
            published_at=utcnow(),
            collected_at=utcnow(),
        )
    )


class TestSchema:
    def test_all_expected_tables_are_created(self, db: Session, settings: Settings) -> None:
        tables = set(inspect(get_engine(settings)).get_table_names())
        assert EXPECTED_TABLES.issubset(tables)

    def test_foreign_keys_are_enforced(self, db: Session) -> None:
        db.add(Article(source_id=9999, url="u", url_hash="h", title="t"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_url_hash_is_unique(self, db: Session) -> None:
        source = _make_source(db)
        _make_article(db, source, url_hash="dup")
        with pytest.raises(IntegrityError):
            _make_article(db, source, url_hash="dup")


class TestCategoryRepository:
    def test_seeds_fifteen_categories(self, db: Session) -> None:
        assert CategoryRepository(db).count() == 15

    def test_seeding_is_idempotent(self, db: Session) -> None:
        repo = CategoryRepository(db)
        assert repo.seed_defaults() == 0
        assert repo.count() == 15

    def test_unknown_slug_falls_back_to_other(self, db: Session) -> None:
        assert CategoryRepository(db).get_or_create("quantum-farming").slug == "other"


class TestSourceRepository:
    def test_upsert_updates_instead_of_duplicating(self, db: Session) -> None:
        repo = SourceRepository(db)
        _make_source(db)
        repo.upsert(slug="techcrunch", name="TechCrunch", feed_url="https://tc.com/feed2")
        assert repo.count() == 1
        assert repo.get_by_slug("techcrunch").feed_url == "https://tc.com/feed2"

    def test_failure_then_success_resets_counter(self, db: Session) -> None:
        repo = SourceRepository(db)
        source = _make_source(db)
        repo.mark_failure(source, "timeout")
        repo.mark_failure(source, "timeout")
        assert source.consecutive_failures == 2
        repo.mark_success(source)
        assert source.consecutive_failures == 0
        assert source.last_error is None

    def test_list_active_excludes_disabled(self, db: Session) -> None:
        repo = SourceRepository(db)
        _make_source(db, "a")
        disabled = _make_source(db, "b")
        disabled.is_active = False
        db.flush()
        assert [s.slug for s in repo.list_active()] == ["a"]


class TestArticleRepository:
    def test_duplicate_linking_increments_mention_count(self, db: Session) -> None:
        repo = ArticleRepository(db)
        source = _make_source(db)
        original = _make_article(db, source, url_hash="one")
        copy = _make_article(db, source, url_hash="two")

        repo.mark_duplicate(copy, original)

        assert copy.is_duplicate is True
        assert copy.duplicate_of_id == original.id
        assert copy.status == ArticleStatus.DUPLICATE
        assert original.mention_count == 2

    def test_status_queue_skips_duplicates(self, db: Session) -> None:
        repo = ArticleRepository(db)
        source = _make_source(db)
        _make_article(db, source, url_hash="a")
        dup = _make_article(db, source, url_hash="b")
        dup.is_duplicate = True
        db.flush()

        queued = repo.list_by_status(ArticleStatus.COLLECTED)
        assert [a.url_hash for a in queued] == ["a"]

    def test_top_scored_orders_by_final_score(self, db: Session) -> None:
        source = _make_source(db)
        articles = ArticleRepository(db)
        scores = ScoreRepository(db)
        low = _make_article(db, source, url_hash="low")
        high = _make_article(db, source, url_hash="high")
        scores.add(Score(article_id=low.id, final_score=12.0))
        scores.add(Score(article_id=high.id, final_score=91.5))

        window_start = utcnow() - timedelta(days=1)
        window_end = utcnow() + timedelta(days=1)
        top = articles.list_top_scored(window_start, window_end, limit=2)
        assert [a.url_hash for a in top] == ["high", "low"]

    def test_mark_reported_excludes_from_next_window(self, db: Session) -> None:
        repo = ArticleRepository(db)
        source = _make_source(db)
        article = _make_article(db, source, url_hash="x")
        article.status = ArticleStatus.ANALYZED
        db.flush()

        start, end = utcnow() - timedelta(days=1), utcnow() + timedelta(days=1)
        assert len(repo.list_for_period(start, end)) == 1
        repo.mark_reported([article])
        assert len(repo.list_for_period(start, end)) == 0

    def test_count_by_status_breakdown(self, db: Session) -> None:
        repo = ArticleRepository(db)
        source = _make_source(db)
        _make_article(db, source, url_hash="a")
        extracted = _make_article(db, source, url_hash="b")
        extracted.status = ArticleStatus.EXTRACTED
        db.flush()

        breakdown = repo.count_by_status()
        assert breakdown[ArticleStatus.COLLECTED] == 1
        assert breakdown[ArticleStatus.EXTRACTED] == 1


class TestCascades:
    def test_deleting_article_removes_its_summary(self, db: Session) -> None:
        source = _make_source(db)
        article = _make_article(db, source, url_hash="a")
        db.add(
            Summary(
                article_id=article.id,
                title_ar="عنوان",
                summary_ar="ملخص",
                key_points=["نقطة"],
                model_name="qwen3:14b",
            )
        )
        db.flush()

        db.delete(article)
        db.flush()
        assert db.query(Summary).count() == 0


class TestJobRepository:
    def test_finish_records_duration_and_status(self, db: Session) -> None:
        repo = JobRepository(db)
        job = repo.start("daily_collect", trigger="cron")
        repo.finish(job, status="success", processed=42, failed=1)

        assert job.finished_at is not None
        assert job.duration_seconds is not None and job.duration_seconds >= 0
        assert job.items_processed == 42
        assert job.items_failed == 1


class TestSettings:
    def test_relative_paths_resolve_against_project_root(self) -> None:
        cfg = Settings(_env_file=None)  # type: ignore[call-arg]
        assert cfg.database_path.is_absolute()

    def test_database_url_is_sqlite(self, settings: Settings) -> None:
        assert settings.database_url.startswith("sqlite:///")

    def test_recipients_are_split_and_trimmed(self) -> None:
        cfg = Settings(email_to=" a@x.com , b@y.com ", _env_file=None)  # type: ignore[call-arg]
        assert cfg.email_recipients == ["a@x.com", "b@y.com"]

    def test_invalid_hour_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            Settings(weekly_report_hour=99, _env_file=None)  # type: ignore[call-arg]
