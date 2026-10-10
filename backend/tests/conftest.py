"""Shared fixtures for the Movie Roast backend test suite.

Environment is configured BEFORE the app is imported so ``app.config.settings`` and the
SQLAlchemy engine point at the dedicated test database. OpenAI and TMDB are replaced by
in-memory fakes for every test (see ``fake_llm`` / ``fake_tmdb``), so the suite never touches
the network.
"""

import os
from pathlib import Path

_LOCAL_TEST_DB = "postgresql://roast:roast@localhost:5433/roast_news_test"


def _pick_test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    existing = os.environ.get("DATABASE_URL", "")
    if "_test" in existing:
        return existing
    return _LOCAL_TEST_DB


os.environ["DATABASE_URL"] = _pick_test_database_url()
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789abcdef"
os.environ["IP_HASH_SALT"] = "test-ip-hash-salt"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["TMDB_API_KEY"] = "test-tmdb-key"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["ENVIRONMENT"] = "test"

# ruff: noqa: E402 - the imports below must run after the environment is configured.
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import make_url, text
from sqlalchemy.orm import Session

from alembic import command
from app.auth.jwt import create_access_token
from app.config import settings
from app.core.rate_limit import limiter, reset_daily_limit
from app.core.security import hash_ip
from app.database import SessionLocal, engine
from app.exceptions import AppError, NotFoundError
from app.main import app
from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.models.user import User
from app.services import gif_client, llm_client, tmdb_client
from app.services.gif_client import Gif
from app.services.llm_client import GeneratedRoast, SensitiveResult
from app.services.tmdb_client import MovieDetails, MovieSummary

BACKEND_DIR = Path(__file__).resolve().parent.parent

FAKE_ROAST_TEXT = (
    "172 minutes padam machan, popcorn rendu thadava vaanga vendiyadhaa pochu! "
    "Hero intro-ku mattum 10 minutes slow motion, logic-a veetla vechitu ponga."
)

MOVIE_ID = 4242

MOVIE = MovieDetails(
    tmdb_id=MOVIE_ID,
    title="Thunder Raja",
    original_title="Thunder Raja",
    year=2019,
    original_language="ta",
    poster_path="/thunder.jpg",
    overview="A village man takes on a corrupt mining baron to save his town.",
    tagline="One man. One village.",
    genres=("Action", "Drama"),
    runtime_minutes=172,
    rating=6.4,
    vote_count=120,
    directors=("K. Director",),
    cast=("Hero Actor", "Heroine Actor"),
)


def _alembic_config() -> Config:
    # No ini file on purpose: env.py would otherwise call fileConfig() and reset app loggers.
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("path_separator", "os")
    return cfg


# --------------------------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _database_schema() -> Iterator[None]:
    """Build the schema with Alembic (proves migrations work); tear it down at the end."""
    db_name = make_url(settings.sqlalchemy_database_url).database or ""
    if not db_name.endswith("_test"):
        pytest.exit(f"Refusing to run tests against non-test database {db_name!r}", returncode=2)

    with engine.begin() as conn:  # start clean even if a previous run crashed mid-way
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    yield
    engine.dispose()
    command.downgrade(cfg, "base")
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    """Truncate every table after each test (robust even though services call commit())."""
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE roasts, refresh_tokens, users RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# --------------------------------------------------------------------------------------------
# Global state resets
# --------------------------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_limits(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    limiter.reset()
    reset_daily_limit()
    # Generous defaults so ordinary tests never trip the limiter; rate-limit tests lower them.
    monkeypatch.setattr(settings, "RATE_LIMIT_ANON", "1000/hour")
    monkeypatch.setattr(settings, "RATE_LIMIT_USER", "1000/hour")
    monkeypatch.setattr(settings, "RATE_LIMIT_SEARCH", "1000/minute")
    monkeypatch.setattr(settings, "DAILY_ROAST_LIMIT", 100000)
    yield
    limiter.reset()
    reset_daily_limit()


@pytest.fixture(autouse=True)
def _reset_openai_client() -> Iterator[None]:
    llm_client._client = None
    yield
    llm_client._client = None


# --------------------------------------------------------------------------------------------
# Fakes for OpenAI + TMDB
# --------------------------------------------------------------------------------------------
@dataclass
class FakeLLM:
    """Programmable stand-in for ``app.services.llm_client``."""

    flagged_texts: set[str] = field(default_factory=set)
    flag_everything: bool = False
    flag_output: bool = False
    sensitive: bool = False
    category: str = "none"
    roast_text: str = FAKE_ROAST_TEXT
    gif_mood: str | None = "facepalm"
    generate_error: Exception | None = None
    moderate_calls: list[str] = field(default_factory=list)
    classify_calls: int = 0
    generate_calls: int = 0

    async def moderate(self, text_: str) -> bool:
        self.moderate_calls.append(text_)
        if self.flag_output and text_ == self.roast_text:
            return True
        return self.flag_everything or text_ in self.flagged_texts

    async def classify_sensitive(self, title: str, context: str) -> SensitiveResult:
        self.classify_calls += 1
        return SensitiveResult(sensitive=self.sensitive, category=self.category)

    async def generate_roast(self, title: str, context: str, spice: SpiceLevel) -> GeneratedRoast:
        self.generate_calls += 1
        if self.generate_error is not None:
            raise self.generate_error
        return GeneratedRoast(text=self.roast_text, gif_mood=self.gif_mood)


@pytest.fixture(autouse=True)
def fake_llm(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    fake = FakeLLM()
    if request.node.get_closest_marker("real_llm") is None:
        monkeypatch.setattr(llm_client, "moderate", fake.moderate)
        monkeypatch.setattr(llm_client, "classify_sensitive", fake.classify_sensitive)
        monkeypatch.setattr(llm_client, "generate_roast", fake.generate_roast)
    return fake


@dataclass
class FakeTMDB:
    """Programmable stand-in for ``app.services.tmdb_client`` (search + details)."""

    movies: dict[int, MovieDetails] = field(default_factory=lambda: {MOVIE_ID: MOVIE})
    error: AppError | None = None
    search_calls: list[str] = field(default_factory=list)
    get_calls: list[int] = field(default_factory=list)

    async def search_movies(self, query: str) -> list[MovieSummary]:
        self.search_calls.append(query)
        if self.error is not None:
            raise self.error
        return [
            MovieSummary(
                tmdb_id=m.tmdb_id,
                title=m.title,
                year=m.year,
                original_language=m.original_language,
                poster_path=m.poster_path,
                overview=m.overview,
            )
            for m in self.movies.values()
            if query.lower() in m.title.lower()
        ]

    async def get_movie(self, tmdb_id: int) -> MovieDetails:
        self.get_calls.append(tmdb_id)
        if self.error is not None:
            raise self.error
        movie = self.movies.get(tmdb_id)
        if movie is None:
            raise NotFoundError(detail="Movie not found")
        return movie


@pytest.fixture(autouse=True)
def fake_tmdb(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> FakeTMDB:
    fake = FakeTMDB()
    tmdb_client.clear_cache()
    if request.node.get_closest_marker("real_tmdb") is None:
        monkeypatch.setattr(tmdb_client, "search_movies", fake.search_movies)
        monkeypatch.setattr(tmdb_client, "get_movie", fake.get_movie)
    return fake


FAKE_GIF = Gif(
    url="https://media1.giphy.com/media/abc123/200.gif",
    page_url="https://giphy.com/gifs/facepalm-abc123",
)


@dataclass
class FakeGifs:
    """Programmable stand-in for ``gif_client.pick_gif``."""

    gif: Gif | None = FAKE_GIF
    calls: list[tuple[str | None, str]] = field(default_factory=list)

    async def pick_gif(self, mood: str | None, seed: str) -> Gif | None:
        self.calls.append((mood, seed))
        return self.gif


@pytest.fixture(autouse=True)
def fake_gifs(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> FakeGifs:
    fake = FakeGifs()
    gif_client.clear_cache()
    if request.node.get_closest_marker("real_gifs") is None:
        monkeypatch.setattr(gif_client, "pick_gif", fake.pick_gif)
    return fake


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "real_llm: do not replace llm_client functions with fakes")
    config.addinivalue_line("markers", "real_tmdb: do not replace tmdb_client functions with fakes")
    config.addinivalue_line("markers", "real_gifs: do not replace gif_client.pick_gif with a fake")


# --------------------------------------------------------------------------------------------
# HTTP client + factories
# --------------------------------------------------------------------------------------------
@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture
def user_factory(db: Session) -> Callable[..., User]:
    counter = {"n": 0}

    def make(
        email: str | None = None,
        *,
        google_id: str | None = None,
        is_active: bool = True,
        full_name: str | None = "Test User",
    ) -> User:
        counter["n"] += 1
        n = counter["n"]
        user = User(
            email=email or f"user{n}@example.com",
            google_id=google_id or f"google-{n}-{uuid.uuid4().hex[:8]}",
            full_name=full_name,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return make


@pytest.fixture
def user(user_factory: Callable[..., User]) -> User:
    return user_factory("machan@example.com")


def make_auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def auth_headers(user: User) -> dict[str, str]:
    return make_auth_headers(user)


@pytest.fixture
def roast_factory(db: Session) -> Callable[..., Roast]:
    def make(
        *,
        user: User | None = None,
        tmdb_id: int = MOVIE_ID,
        spice: SpiceLevel = SpiceLevel.medium,
        status: RoastStatus = RoastStatus.completed,
        roast_text: str | None = FAKE_ROAST_TEXT,
        refusal_reason: str | None = None,
        created_at: datetime | None = None,
    ) -> Roast:
        kwargs: dict[str, Any] = {}
        if created_at is not None:
            kwargs["created_at"] = created_at
        roast = Roast(
            user_id=user.id if user is not None else None,
            tmdb_id=tmdb_id,
            movie_title=MOVIE.title,
            release_year=MOVIE.year,
            original_language=MOVIE.original_language,
            poster_path=MOVIE.poster_path,
            spice_level=spice,
            roast_text=roast_text if status == RoastStatus.completed else None,
            status=status,
            refusal_reason=refusal_reason,
            model="gpt-4o-mini",
            client_ip_hash=hash_ip("127.0.0.1"),
            **kwargs,
        )
        db.add(roast)
        db.commit()
        db.refresh(roast)
        return roast

    return make
