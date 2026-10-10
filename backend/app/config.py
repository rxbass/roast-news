"""Application settings loaded from environment variables (and an optional .env file)."""

from pathlib import Path
from typing import Annotated, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent

# Look for .env in the backend dir and the repo root; missing files are ignored.
_ENV_FILES = (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"
    OPENAI_TIMEOUT_SECONDS: int = 30

    # TMDB (movie data). A v3 API key or a v4 read-access token (starts with "eyJ").
    TMDB_API_KEY: str = ""
    TMDB_TIMEOUT_SECONDS: int = 10

    # GIPHY (reaction GIFs). Optional: empty disables GIFs.
    GIPHY_API_KEY: str = ""
    GIPHY_TIMEOUT_SECONDS: int = 5

    # Limits & safety
    RATE_LIMIT_ANON: str = "5/hour"
    RATE_LIMIT_USER: str = "20/hour"
    DAILY_ROAST_LIMIT: int = 1000
    ROAST_CACHE_HOURS: int = 24
    RATE_LIMIT_SEARCH: str = "60/minute"
    IP_HASH_SALT: str
    # Number of reverse proxies in front of the API that append to X-Forwarded-For.
    # 0 (default) = the API is exposed directly, so the header is ignored (it's spoofable).
    TRUSTED_PROXY_COUNT: int = 0

    # URLs / CORS
    FRONTEND_URL: str = "http://localhost:5173"
    # Accepts a JSON list or a comma-separated string in the environment.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    ENVIRONMENT: str = "development"

    @model_validator(mode="after")
    def _check_production_secrets(self) -> Self:
        """Refuse to boot in production with placeholder or weak security settings.

        A public placeholder SECRET_KEY would let anyone forge access tokens for any user.
        """
        if not self.is_production:
            return self
        problems: list[str] = []
        if len(self.SECRET_KEY) < 32 or "change-me" in self.SECRET_KEY:
            problems.append("SECRET_KEY must be a random value of at least 32 characters")
        if len(self.IP_HASH_SALT) < 16 or "change-me" in self.IP_HASH_SALT:
            problems.append("IP_HASH_SALT must be a random value of at least 16 characters")
        if self.ALGORITHM not in {"HS256", "HS384", "HS512"}:
            problems.append("ALGORITHM must be one of HS256, HS384, HS512")
        if not self.FRONTEND_URL.startswith("https://"):
            problems.append("FRONTEND_URL must use https:// in production")
        if problems:
            raise ValueError("Unsafe production settings: " + "; ".join(problems))
        return self

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                import json

                return json.loads(raw)
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @property
    def allowed_origins(self) -> list[str]:
        """CORS origins plus FRONTEND_URL, de-duplicated, order preserved."""
        origins = [*self.CORS_ORIGINS, self.FRONTEND_URL]
        return list(dict.fromkeys(o.rstrip("/") for o in origins if o))

    @property
    def sqlalchemy_database_url(self) -> str:
        """DATABASE_URL with an explicit psycopg (v3) driver, whatever scheme the env uses.

        SQLAlchemy 2.0 maps bare ``postgresql://`` to psycopg2 but 2.1 maps it to psycopg v3,
        so pin the driver here instead of relying on the installed SQLAlchemy's default.
        """
        url = self.DATABASE_URL
        for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


settings = Settings()  # required fields (DATABASE_URL, SECRET_KEY, IP_HASH_SALT) come from env
