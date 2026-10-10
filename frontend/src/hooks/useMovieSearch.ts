import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { searchMovies } from '../services/movieService';
import type { MovieSearchResult } from '../types/roast';

/** Searches shorter than this aren't sent (too many junk matches). */
export const MIN_SEARCH_LENGTH = 2;
const DEBOUNCE_MS = 300;

/** `value`, but only after it has stopped changing for `delayMs`. */
export function useDebouncedValue<T>(value: T, delayMs: number = DEBOUNCE_MS): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** Debounced TMDB-backed movie search for the roast form. */
export function useMovieSearch(query: string): UseQueryResult<MovieSearchResult[], unknown> {
  const term = useDebouncedValue(query.trim().replace(/\s+/g, ' '));
  return useQuery({
    queryKey: ['movies', 'search', term.toLowerCase()],
    queryFn: ({ signal }) => searchMovies(term, signal),
    enabled: term.length >= MIN_SEARCH_LENGTH,
    staleTime: 10 * 60 * 1000,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
