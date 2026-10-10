import { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';

import type { MovieSearchResult, Roast } from '../../types/roast';

export function makeRoast(overrides: Partial<Roast> = {}): Roast {
  return {
    id: '7f8c1c1e-1111-4222-8333-944455556666',
    movie: {
      tmdb_id: 4242,
      title: 'Thunder Raja',
      year: 2019,
      original_language: 'ta',
      poster_url: 'https://image.tmdb.org/t/p/w342/thunder.jpg',
    },
    spice_level: 'medium',
    roast_text: '172 minutes padam machan, popcorn rendu thadava!\nHero intro-ku mattum 10 minutes slow motion 😂',
    gif: {
      url: 'https://media1.giphy.com/media/abc123/200.gif',
      page_url: 'https://giphy.com/gifs/facepalm-abc123',
    },
    status: 'completed',
    refusal_reason: null,
    message: null,
    cached: false,
    created_at: '2026-10-10T10:00:00Z',
    ...overrides,
  };
}

export function makeMovieResult(overrides: Partial<MovieSearchResult> = {}): MovieSearchResult {
  return {
    tmdb_id: 4242,
    title: 'Thunder Raja',
    year: 2019,
    original_language: 'ta',
    poster_url: 'https://image.tmdb.org/t/p/w342/thunder.jpg',
    overview: 'A village man takes on a corrupt mining baron.',
    ...overrides,
  };
}

/** Build an AxiosError that getErrorInfo() understands. */
export function makeAxiosError(
  status: number,
  data: Record<string, unknown> = { detail: 'error' },
  headers: Record<string, string> = {},
): AxiosError {
  const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
  const response: AxiosResponse = {
    status,
    statusText: String(status),
    data,
    headers,
    config,
  };
  return new AxiosError(`Request failed with status code ${status}`, String(status), config, null, response);
}
