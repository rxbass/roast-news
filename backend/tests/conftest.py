"""Shared fixtures for the Roast News backend test suite.

Environment is configured BEFORE the app is imported so ``app.config.settings`` and the
SQLAlchemy engine point at the dedicated test database. OpenAI and the article scraper are
replaced by in-memory fakes for every test (see ``fake_llm`` / ``fake_scraper``), so the suite
never touches the network.
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
from app.exceptions import AppError
from app.main import app
from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.models.user import User
from app.services import llm_client, roast_service
from app.services.llm_client import SensitiveResult
from app.services.scraper_service import Article
from app.services.url_utils import normalize_url, url_hash

BACKEND_DIR = Path(__file__).resolve().parent.parent

FAKE_ROAST_TEXT = (
    "Machan, indha news paatha udane en filter coffee-ae cold aayiduchu! "
    "Corporation-la meeting pottu meeting pottu, road mattum appadiye irukku da."
)

ARTICLE_TEXT = (
    "The city corporation announced on Monday that it will hold another meeting to discuss "
    "the long-pending road repair project in the neighbourhood. Residents said they have "
    "heard the same promise many times over the last five years, while officials insisted "
    "that this time the funds have finally been sanctioned and work will begin soon."
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
# Fakes for OpenAI + scraper
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
    generate_error: Exception | None = None
    moderate_calls: list[str] = field(default_factory=list)
    classify_calls: int = 0
    generate_calls: int = 0

    async def moderate(self, text_: str) -> bool:
        self.moderate_calls.append(text_)
        if self.flag_output and text_ == self.roast_text:
            return True
        return self.flag_everything or text_ in self.flagged_texts

    async def classify_sensitive(self, title: str, text_: str) -> SensitiveResult:
        self.classify_calls += 1
        return SensitiveResult(sensitive=self.sensitive, category=self.category)

    async def generate_roast(self, title: str, text_: str, spice: SpiceLevel) -> str:
        self.generate_calls += 1
        if self.generate_error is not None:
            raise self.generate_error
        return self.roast_text


@dataclass
class FakeScraper:
    """Programmable stand-in for ``roast_service.fetch_article``."""

    title: str = "Corporation to hold yet another meeting on road repairs"
    text: str = ARTICLE_TEXT
    error: AppError | None = None
    calls: list[str] = field(default_factory=list)

    async def fetch_article(self, url: str) -> Article:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        domain = normalize_url(url).split("/")[2].removeprefix("www.")
        return Article(title=self.title, text=self.text, domain=domain, final_url=url)


@pytest.fixture(autouse=True)
def fake_llm(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    fake = FakeLLM()
    if request.node.get_closest_marker("real_llm") is None:
        monkeypatch.setattr(llm_client, "moderate", fake.moderate)
        monkeypatch.setattr(llm_client, "classify_sensitive", fake.classify_sensitive)
        monkeypatch.setattr(llm_client, "generate_roast", fake.generate_roast)
    return fake


@pytest.fixture(autouse=True)
def fake_scraper(monkeypatch: pytest.MonkeyPatch) -> FakeScraper:
    fake = FakeScraper()
    monkeypatch.setattr(roast_service, "fetch_article", fake.fetch_article)
    return fake


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "real_llm: do not replace llm_client functions with fakes")


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
        url: str = "https://news.example.com/story",
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
            source_url=url,
            url_hash=url_hash(normalize_url(url)),
            source_domain="news.example.com",
            article_title="A headline",
            article_excerpt=ARTICLE_TEXT[:300],
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
