"""Roasts router (thin: validation + wiring; logic lives in ``services.roast_service``).

DB-only endpoints are plain ``def`` so FastAPI runs their blocking SQLAlchemy calls in its
threadpool instead of on the event loop. ``create_roast`` must stay async (it awaits the scraper
and OpenAI); its DB calls are short and the connection is released before the slow awaits.

Route order matters: ``/me`` is registered before ``/{roast_id}``.
"""

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_optional_user
from app.core.rate_limit import dynamic_limit, get_client_ip, limiter
from app.database import get_db
from app.models.user import User
from app.schemas.roast import RoastCreate, RoastListResponse, RoastResponse
from app.services import roast_service

router = APIRouter(prefix="/api/v1/roasts", tags=["roasts"])


@router.post("", response_model=RoastResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(dynamic_limit)
async def create_roast(
    request: Request,
    response: Response,
    data: RoastCreate,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> RoastResponse:
    """Create a roast (201, incl. refused) or return a cached one (200)."""
    result = await roast_service.create_roast(
        db,
        url=str(data.url),
        spice=data.spice_level,
        user=user,
        client_ip=get_client_ip(request),
    )
    if result.cached:
        response.status_code = status.HTTP_200_OK
    return RoastResponse.from_roast(result.roast, cached=result.cached)


@router.get("/me", response_model=RoastListResponse)
def list_my_roasts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoastListResponse:
    """The signed-in user's roast history, newest first."""
    rows, total = roast_service.list_user_roasts(db, user, page=page, size=size)
    return RoastListResponse(
        items=[RoastResponse.from_roast(row) for row in rows],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{roast_id}", response_model=RoastResponse)
def get_roast(roast_id: str, db: Session = Depends(get_db)) -> RoastResponse:
    """Public permalink fetch; unknown or malformed ids -> 404."""
    return RoastResponse.from_roast(roast_service.get_roast(db, roast_id))


@router.delete("/{roast_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_roast(
    roast_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete one of the current user's roasts; anything else -> 404."""
    roast_service.delete_user_roast(db, user, roast_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
