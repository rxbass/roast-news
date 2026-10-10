import axios, { AxiosHeaders, isAxiosError, type InternalAxiosRequestConfig } from 'axios';

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../lib/tokenStorage';
import type { TokenPair } from '../types';

/** Root of the backend (no trailing slash), e.g. http://localhost:8000 */
export const API_URL: string = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(
  /\/+$/,
  '',
);

/** All API routes live under /api/v1. */
export const API_BASE_URL = `${API_URL}/api/v1`;

/** Error body shape returned by the FastAPI backend. */
export interface ApiError {
  detail: string;
  message?: string | null;
}

export interface ErrorInfo {
  status: number | null;
  detail: string;
  message: string | null;
  retryAfter: number | null;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Attach the bearer token (if any) to every request.
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    const headers = AxiosHeaders.from(config.headers);
    headers.set('Authorization', `Bearer ${token}`);
    config.headers = headers;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Auth: 401 -> refresh (single-flight) -> retry once.
// ---------------------------------------------------------------------------

/** Window event fired when the session can no longer be refreshed. */
export const AUTH_EXPIRED_EVENT = 'roastnews:auth-expired';

/** Endpoints whose 401s must never trigger a refresh (avoids loops). */
const NO_REFRESH_PATHS = ['/auth/refresh', '/auth/logout'];

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

function isTokenPair(value: unknown): value is TokenPair {
  return (
    isRecord(value) &&
    typeof value.access_token === 'string' &&
    typeof value.refresh_token === 'string'
  );
}

/**
 * POST /auth/refresh using the *plain* axios instance (no interceptors on `api`
 * are involved, so a failing refresh can't recurse). Rotation: the returned
 * refresh token replaces the old one.
 */
export async function refreshTokens(refreshToken: string): Promise<TokenPair> {
  const { data } = await axios.post<unknown>(
    `${API_BASE_URL}/auth/refresh`,
    { refresh_token: refreshToken },
    { headers: { 'Content-Type': 'application/json', Accept: 'application/json' } },
  );
  if (!isTokenPair(data)) {
    throw new Error('Invalid token response from /auth/refresh');
  }
  return data;
}

let refreshInFlight: Promise<TokenPair> | null = null;

/**
 * Rotate `refreshToken`, unless another tab already did: tokens live in shared
 * localStorage, so if the stored refresh token changed we reuse that pair instead
 * of replaying the old (now revoked) token, which the backend treats as theft.
 */
async function rotateIfStillCurrent(refreshToken: string): Promise<TokenPair> {
  const current = getRefreshToken();
  const access = getAccessToken();
  if (current && current !== refreshToken && access) {
    return { access_token: access, refresh_token: current, token_type: 'bearer' };
  }
  const pair = await refreshTokens(refreshToken);
  setTokens(pair.access_token, pair.refresh_token);
  return pair;
}

/**
 * Refresh once; concurrent callers in this tab share the in-flight promise, and
 * the Web Locks API (where available) serialises refreshes across tabs.
 */
function refreshOnce(refreshToken: string): Promise<TokenPair> {
  if (!refreshInFlight) {
    const run = (): Promise<TokenPair> => rotateIfStillCurrent(refreshToken);
    const locked = async (): Promise<TokenPair> =>
      typeof navigator !== 'undefined' && navigator.locks
        ? await navigator.locks.request('roastnews-refresh', run)
        : run();
    refreshInFlight = locked().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

function notifyAuthExpired(): void {
  clearTokens();
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

function isNoRefreshUrl(url: string | undefined): boolean {
  if (!url) return false;
  const path = url.split('?')[0];
  return NO_REFRESH_PATHS.some((p) => path.endsWith(p));
}

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!isAxiosError(error) || error.response?.status !== 401 || !error.config) {
      return Promise.reject(error);
    }
    const original: RetriableConfig = error.config;
    if (original._retry || isNoRefreshUrl(original.url)) {
      return Promise.reject(error);
    }

    // The request went out with an access token that has since been replaced (another
    // tab or request refreshed meanwhile): just retry with the current one.
    const currentAccess = getAccessToken();
    const sentAuth = AxiosHeaders.from(original.headers).get('Authorization');
    if (currentAccess && typeof sentAuth === 'string' && sentAuth !== `Bearer ${currentAccess}`) {
      original._retry = true;
      const headers = AxiosHeaders.from(original.headers);
      headers.set('Authorization', `Bearer ${currentAccess}`);
      original.headers = headers;
      return api(original);
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      // A stale access token with no way to refresh: drop the session.
      if (getAccessToken()) notifyAuthExpired();
      return Promise.reject(error);
    }

    original._retry = true;
    let pair: TokenPair;
    try {
      pair = await refreshOnce(refreshToken);
    } catch (refreshError: unknown) {
      // Only a rejected refresh token ends the session; 429/5xx/network errors are
      // transient, so keep the tokens and let the caller see the original 401.
      if (isAxiosError(refreshError) && refreshError.response?.status === 401) {
        notifyAuthExpired();
      }
      return Promise.reject(error);
    }

    const headers = AxiosHeaders.from(original.headers);
    headers.set('Authorization', `Bearer ${pair.access_token}`);
    original.headers = headers;
    return api(original);
  },
);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function parseRetryAfter(raw: unknown): number | null {
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'string' && raw.trim() !== '') {
    const seconds = Number(raw);
    if (Number.isFinite(seconds)) return seconds;
    const date = Date.parse(raw);
    if (!Number.isNaN(date)) return Math.max(0, Math.ceil((date - Date.now()) / 1000));
  }
  return null;
}

function extractDetail(data: unknown): string | null {
  if (typeof data === 'string') return data.trim() ? data : null;
  if (!isRecord(data)) return null;
  const { detail } = data;
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors: detail is a list of { msg, loc, ... }
  if (Array.isArray(detail) && detail.length > 0) {
    const first: unknown = detail[0];
    if (isRecord(first) && typeof first.msg === 'string') return first.msg;
  }
  return null;
}

/** Normalize any thrown value (axios or otherwise) into a predictable shape. */
export function getErrorInfo(err: unknown): ErrorInfo {
  if (isAxiosError(err)) {
    const status = err.response?.status ?? null;
    const data: unknown = err.response?.data;
    const message = isRecord(data) && typeof data.message === 'string' ? data.message : null;
    const headers: unknown = err.response?.headers;
    const retryAfter = isRecord(headers) ? parseRetryAfter(headers['retry-after']) : null;
    const detail =
      extractDetail(data) ??
      (status === null ? 'Network error. Is the server running?' : err.message || 'Request failed');
    return { status, detail, message, retryAfter };
  }
  if (err instanceof Error) {
    return { status: null, detail: err.message, message: null, retryAfter: null };
  }
  return { status: null, detail: 'Something went wrong', message: null, retryAfter: null };
}

export default api;
