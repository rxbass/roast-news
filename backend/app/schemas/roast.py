"""Roast request/response schemas (JSON field names are the frontend contract)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl, UrlConstraints, field_validator

from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.services.safety_service import FAILURE_LINE, refusal_message

MAX_URL_LENGTH = 2048

RoastUrl = Annotated[
    HttpUrl, UrlConstraints(max_length=MAX_URL_LENGTH, allowed_schemes=["http", "https"])
]


class RoastCreate(BaseModel):
    """Body of ``POST /api/v1/roasts``."""

    url: RoastUrl
    spice_level: SpiceLevel = SpiceLevel.medium

    @field_validator("url")
    @classmethod
    def _encoded_length(cls, url: HttpUrl) -> HttpUrl:
        # UrlConstraints checks the raw input; percent-encoding non-ASCII (e.g. a Tamil slug,
        # 9 chars per letter) can grow it far past the 2048-char ``source_url`` column.
        if len(str(url)) > MAX_URL_LENGTH:
            raise ValueError(f"URL is too long once encoded (max {MAX_URL_LENGTH} characters)")
        return url


class RoastResponse(BaseModel):
    """A roast as returned by every roast endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_url: str
    source_domain: str
    article_title: str
    spice_level: SpiceLevel
    roast_text: str | None
    status: RoastStatus
    refusal_reason: str | None
    message: str | None = None
    cached: bool = False
    created_at: datetime

    @classmethod
    def from_roast(cls, roast: Roast, *, cached: bool = False) -> "RoastResponse":
        """Build the response, deriving ``message`` deterministically from the roast id."""
        message: str | None = None
        if roast.status == RoastStatus.refused:
            message = refusal_message(roast.refusal_reason, str(roast.id))
        elif roast.status == RoastStatus.failed:
            message = FAILURE_LINE
        return cls(
            id=roast.id,
            source_url=roast.source_url,
            source_domain=roast.source_domain,
            # Refused/failed pages may be abusive: don't republish their title on our permalink.
            article_title=roast.article_title if roast.status == RoastStatus.completed else "",
            spice_level=roast.spice_level,
            roast_text=roast.roast_text if roast.status == RoastStatus.completed else None,
            status=roast.status,
            refusal_reason=roast.refusal_reason,
            message=message,
            cached=cached,
            created_at=roast.created_at,
        )


class RoastListResponse(BaseModel):
    """Paginated roast history (``GET /api/v1/roasts/me``)."""

    items: list[RoastResponse]
    total: int
    page: int
    size: int
