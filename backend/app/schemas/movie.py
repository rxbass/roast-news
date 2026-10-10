"""Movie schemas (JSON field names are the frontend contract)."""

from pydantic import BaseModel

from app.services.tmdb_client import MovieSummary, poster_url


class MovieInfo(BaseModel):
    """The movie a roast is about."""

    tmdb_id: int
    title: str
    year: int | None
    original_language: str
    poster_url: str | None


class MovieSearchResult(MovieInfo):
    """One search result (``GET /api/v1/movies/search``)."""

    overview: str

    @classmethod
    def from_summary(cls, movie: MovieSummary) -> "MovieSearchResult":
        """Build the response item from a TMDB search summary."""
        return cls(
            tmdb_id=movie.tmdb_id,
            title=movie.title,
            year=movie.year,
            original_language=movie.original_language,
            poster_url=poster_url(movie.poster_path),
            overview=movie.overview,
        )


class MovieSearchResponse(BaseModel):
    """Search results, best match first (Tamil films ranked ahead)."""

    results: list[MovieSearchResult]
