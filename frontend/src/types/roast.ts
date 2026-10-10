// Backend returns snake_case JSON; these types mirror it exactly (no mapping layer).

export type SpiceLevel = 'mild' | 'medium' | 'extra_spicy';

export type RoastStatus = 'completed' | 'refused' | 'failed';

/** The movie a roast is about (snapshot taken from TMDB at roast time). */
export interface Movie {
  tmdb_id: number;
  title: string;
  year: number | null;
  original_language: string;
  poster_url: string | null;
}

/** One result of GET /movies/search. */
export interface MovieSearchResult extends Movie {
  overview: string;
}

export interface MovieSearchResponse {
  results: MovieSearchResult[];
}

/** Reaction GIF shown with a roast; `page_url` links back to GIPHY for attribution. */
export interface RoastGif {
  url: string;
  page_url: string;
}

export interface Roast {
  id: string;
  movie: Movie;
  spice_level: SpiceLevel;
  roast_text: string | null;
  gif: RoastGif | null;
  status: RoastStatus;
  refusal_reason: string | null;
  message: string | null;
  cached: boolean;
  created_at: string;
}

export interface RoastCreate {
  tmdb_id: number;
  spice_level: SpiceLevel;
}

export interface RoastList {
  items: Roast[];
  total: number;
  page: number;
  size: number;
}
