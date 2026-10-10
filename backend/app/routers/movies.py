"""Movies router: TMDB-backed search for the roast form."""

from fastapi import APIRouter, Query, Request

from app.core.rate_limit import limiter, search_limit
from app.schemas.movie import MovieSearchResponse, MovieSearchResult
from app.services import tmdb_client

router = APIRouter(prefix="/api/v1/movies", tags=["movies"])


@router.get("/search", response_model=MovieSearchResponse)
@limiter.limit(search_limit)
async def search_movies(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
) -> MovieSearchResponse:
    """Search movies by title; Tamil films first, adult titles excluded."""
    results = await tmdb_client.search_movies(q)
    return MovieSearchResponse(results=[MovieSearchResult.from_summary(m) for m in results])
