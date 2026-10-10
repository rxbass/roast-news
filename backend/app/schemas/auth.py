"""Auth request/response schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    """Access + refresh token pair returned by the OAuth callback (via redirect) and /refresh."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret


class RefreshRequest(BaseModel):
    """Body of POST /api/v1/auth/refresh."""

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    """Body of POST /api/v1/auth/logout."""

    refresh_token: str = Field(min_length=1, max_length=512)
