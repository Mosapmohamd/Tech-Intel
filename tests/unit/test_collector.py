"""Tests for the source catalogue loader and the Collector Agent."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.agents.collector import CollectorAgent
from app.agents.collector.rss.client import FeedResponse
from app.core.config import Settings, SourceConfig, load_sources
from app.core.config.loader import append_source
from app.core.models import ArticleStatus, JobStatus
from app.core.repositories import ArticleRepository, JobRepository, SourceRepository
from tests.unit.test_collection_utils import RSS_FEED

CATALOGUE_YAML = """
defaults:
  quality_weight: 0.5
  is_active: true
groups:
  ai:
    default_category: ai
    sources:
      - slug: alpha
        name: Alpha Blog
        feed_url: https://alpha.example.com/feed
      - slug: beta
        name: Beta Blog
        feed_url: https://beta.example.com/feed
        quality_weight: 0.95
        default_category: research
  security:
    default_category: cybersecurity
    sources:
      - slug: gamma
        name: Gamma Security
        feed_url: https://gamma.example.com/feed
        is_active: false
"""


class StubClient:
    """A FeedClient stand-in returning scripted responses."""

    def __init__(self, responses: dict[str, FeedResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str | None]] = []

    def fetch(
        self, url: str, *, etag: str | None = None, last_modified: str | None = None
    ) -> FeedResponse:
        self.calls.append((url, etag))
        outcome = self.responses[url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        return None


@pytest.fixture
def catalogue_file(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(CATALOGUE_YAML, encoding="utf-8")
    return path


def _ok(url: str, body: bytes = RSS_FEED, etag: str | None = 'W/"v1"') -> FeedResponse:
    return FeedResponse(url=url, status_code=200, body=body, etag=etag)


class TestCatalogueLoader:
    def test_flattens_groups_into_sources(self, catalogue_file: Path) -> None:
        catalogue = load_sources(catalogue_file)
        assert {s.slug for s in catalogue.sources} == {"alpha", "beta", "gamma"}

    def test_group_name_is_attached(self, catalogue_file: Path) -> None:
        assert load_sources(catalogue_file).by_slug("gamma").group == "security"

    def test_source_value_overrides_group_default(self, catalogue_file: Path) -> None:
        catalogue = load_sources(catalogue_file)
        assert catalogue.by_slug("alpha").default_category == "ai"
        assert catalogue.by_slug("beta").default_category == "research"

    def test_group_default_overrides_file_default(self, catalogue_file: Path) -> None:
        catalogue = load_sources(catalogue_file)
        assert catalogue.by_slug("alpha").quality_weight == 0.5
        assert catalogue.by_slug("beta").quality_weight == 0.95

    def test_active_filter(self, catalogue_file: Path) -> None:
        assert {s.slug for s in load_sources(catalogue_file).active()} == {"alpha", "beta"}

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_sources(tmp_path / "nope.yaml")

    def test_duplicate_slug_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "dup.yaml"
        path.write_text(
            "groups:\n  a:\n    sources:\n"
            "      - {slug: x, name: X, feed_url: 'https://x.com/f'}\n"
            "      - {slug: x, name: Y, feed_url: 'https://y.com/f'}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Duplicate source slug"):
            load_sources(path)

    def test_non_http_url_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="http"):
            SourceConfig(slug="x", name="X", feed_url="ftp://x.com/feed")

    def test_unknown_category_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            SourceConfig(
                slug="x", name="X", feed_url="https://x.com/f", default_category="astrology"
            )

    def test_append_writes_a_reloadable_entry(self, catalogue_file: Path) -> None:
        append_source(
            SourceConfig(
                slug="delta", name="Delta", feed_url="https://d.example.com/f", group="ai"
            ),
            path=catalogue_file,
        )
        reloaded = load_sources(catalogue_file)
        assert reloaded.by_slug("delta") is not None
        assert reloaded.by_slug("delta").group == "ai"

    def test_append_rejects_existing_slug(self, catalogue_file: Path) -> None:
        with pytest.raises(ValueError, match="already exists"):
            append_source(
                SourceConfig(slug="alpha", name="A", feed_url="https://a.com/f", group="ai"),
                path=catalogue_file,
            )

    def test_append_preserves_the_comment_header(self, tmp_path: Path) -> None:
        path = tmp_path / "commented.yaml"
        path.write_text(
            "# Header line one\n# Header line two\n\n" + CATALOGUE_YAML, encoding="utf-8"
        )
        append_source(
            SourceConfig(
                slug="delta", name="Delta", feed_url="https://d.example.com/f", group="ai"
            ),
            path=path,
        )
        assert path.read_text(encoding="utf-8").startswith("# Header line one")
        assert load_sources(path).by_slug("delta") is not None

    def test_real_catalogue_is_valid(self) -> None:
        """The shipped sources.yaml must always parse — guards against typos."""
        catalogue = load_sources(Settings(_env_file=None).sources_file)  # type: ignore[call-arg]
        assert len(catalogue.sources) >= 26
        assert len({s.slug for s in catalogue.sources}) == len(catalogue.sources)


class TestCollectorAgent:
    def _agent(
        self, db: Session, settings: Settings, catalogue_file: Path, client: StubClient
    ) -> CollectorAgent:
        return CollectorAgent(
            db,
            settings=settings,
            client=client,  # type: ignore[arg-type]
            catalogue=load_sources(catalogue_file),
        )

    def test_sync_creates_rows_and_is_idempotent(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        agent = self._agent(db, settings, catalogue_file, StubClient({}))
        agent.sync_catalogue()
        agent.sync_catalogue()
        assert SourceRepository(db).count() == 3

    def test_collect_stores_new_articles(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": _ok("https://alpha.example.com/feed"),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        result = agent.collect()

        assert result.sources_total == 2  # gamma is inactive
        assert result.new_articles == 2  # both feeds share the same 2 URLs
        assert ArticleRepository(db).count() == 2

    def test_stored_articles_start_in_collected_state(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": _ok("https://alpha.example.com/feed"),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        agent.collect()

        article = ArticleRepository(db).list_by_status(ArticleStatus.COLLECTED)[0]
        assert article.content is None  # extraction is phase 4
        assert article.feed_summary is not None
        assert article.published_at is not None

    def test_second_run_finds_no_new_articles(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": _ok("https://alpha.example.com/feed"),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        agent.collect()
        second = agent.collect()

        assert second.new_articles == 0
        assert second.duplicates == 4
        assert ArticleRepository(db).count() == 2

    def test_failing_source_does_not_stop_the_others(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": ConnectionError("DNS failure"),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        result = agent.collect()

        assert result.sources_failed == 1
        assert result.new_articles == 2
        failed = SourceRepository(db).get_by_slug("alpha")
        assert failed.consecutive_failures == 1
        assert "DNS failure" in failed.last_error

    def test_partial_failure_marks_job_partial(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": ConnectionError("boom"),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        agent.collect()

        assert JobRepository(db).list_recent(1)[0].status == JobStatus.PARTIAL

    def test_total_failure_marks_job_failed(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": ConnectionError("boom"),
                "https://beta.example.com/feed": ConnectionError("boom"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        agent.collect()

        assert JobRepository(db).list_recent(1)[0].status == JobStatus.FAILED

    def test_etag_is_stored_and_replayed(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": _ok("https://alpha.example.com/feed"),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        agent.collect()
        assert SourceRepository(db).get_by_slug("alpha").etag == 'W/"v1"'

        agent.collect()
        alpha_calls = [etag for url, etag in client.calls if "alpha" in url]
        assert alpha_calls[-1] == 'W/"v1"'

    def test_not_modified_skips_parsing_and_clears_failures(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient(
            {
                "https://alpha.example.com/feed": FeedResponse(
                    "https://alpha.example.com/feed", 304, b""
                ),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        result = agent.collect()

        assert result.sources_unchanged == 1
        assert result.new_articles == 2
        assert SourceRepository(db).get_by_slug("alpha").last_success_at is not None

    def test_per_source_limit_is_respected(
        self, db: Session, catalogue_file: Path, tmp_path: Path
    ) -> None:
        limited = Settings(
            database_path=tmp_path / "limit.db",
            log_dir=tmp_path / "logs",
            max_articles_per_source=1,
            _env_file=None,  # type: ignore[call-arg]
        )
        client = StubClient(
            {
                "https://alpha.example.com/feed": _ok("https://alpha.example.com/feed"),
                "https://beta.example.com/feed": _ok("https://beta.example.com/feed"),
            }
        )
        agent = self._agent(db, limited, catalogue_file, client)
        agent.sync_catalogue()
        result = agent.collect()
        assert result.new_articles == 1

    def test_only_filter_targets_one_source(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        client = StubClient({"https://beta.example.com/feed": _ok("https://beta.example.com/feed")})
        agent = self._agent(db, settings, catalogue_file, client)
        agent.sync_catalogue()
        result = agent.collect(only="beta")

        assert result.sources_total == 1
        assert [url for url, _ in client.calls] == ["https://beta.example.com/feed"]

    def test_unknown_slug_raises(
        self, db: Session, settings: Settings, catalogue_file: Path
    ) -> None:
        agent = self._agent(db, settings, catalogue_file, StubClient({}))
        agent.sync_catalogue()
        with pytest.raises(ValueError, match="Unknown source slug"):
            agent.collect(only="does-not-exist")
