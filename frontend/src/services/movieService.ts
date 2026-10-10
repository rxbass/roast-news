import type { MovieSearchResult, MovieSearchResponse } from '../types/roast';
import api from './api';

/** GET /movies/search?q= -> best matches first (Tamil films ranked ahead). */
export async function searchMovies(query: string, signal?: AbortSignal): Promise<MovieSearchResult[]> {
  const { data } = await api.get<MovieSearchResponse>('/movies/search', {
    params: { q: query },
    signal,
  });
  return data.results;
}

export const movieService = { searchMovies };

export default movieService;
