"""Roast request/response schemas (JSON field names are the frontend contract)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RoastStatus, SpiceLevel
from app.models.roast import Roast
from app.schemas.movie import MovieInfo
from app.services.safety_service import FAILURE_LINE, refusal_message
from app.services.tmdb_client import poster_url

# TMDB ids are positive integers; the upper bound just keeps junk out of the int4 column.
MAX_TMDB_ID = 2_000_000_000


class RoastCreate(BaseModel):
    """Body of ``POST /api/v1/roasts``."""

    tmdb_id: int = Field(ge=1, le=MAX_TMDB_ID)
    spice_level: SpiceLevel = SpiceLevel.medium


class GifInfo(BaseModel):
    """Reaction GIF shown with a roast (``page_url`` links back to GIPHY for attribution)."""

    url: str
    page_url: str


class RoastResponse(BaseModel):
    """A roast as returned by every roast endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movie: MovieInfo
    spice_level: SpiceLevel
    roast_text: str | None
    gif: GifInfo | None = None
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
            movie=MovieInfo(
                tmdb_id=roast.tmdb_id,
                title=roast.movie_title,
                year=roast.release_year,
                original_language=roast.original_language,
                poster_url=poster_url(roast.poster_path),
            ),
            spice_level=roast.spice_level,
            roast_text=roast.roast_text if roast.status == RoastStatus.completed else None,
            gif=(
                GifInfo(url=roast.gif_url, page_url=roast.gif_page_url)
                if roast.status == RoastStatus.completed and roast.gif_url and roast.gif_page_url
                else None
            ),
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
