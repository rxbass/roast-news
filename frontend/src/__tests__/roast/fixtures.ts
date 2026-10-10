import { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';

import type { Roast } from '../../types/roast';

export function makeRoast(overrides: Partial<Roast> = {}): Roast {
  return {
    id: '7f8c1c1e-1111-4222-8333-944455556666',
    source_url: 'https://news.example.com/story/123',
    source_domain: 'news.example.com',
    article_title: 'City announces new flyover after 10 years of planning',
    spice_level: 'medium',
    roast_text: 'Enna da idhu, 10 years planning-a?\nFlyover ready aagum bodhu naanga retire aagiduvom 😂',
    status: 'completed',
    refusal_reason: null,
    message: null,
    cached: false,
    created_at: '2026-10-10T10:00:00Z',
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
