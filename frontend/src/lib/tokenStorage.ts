/**
 * Small wrapper around localStorage for JWT tokens.
 * Every access is wrapped in try/catch because storage can be unavailable
 * (private mode, blocked site data, tests).
 */
const ACCESS_TOKEN_KEY = 'roastnews.access_token';
const REFRESH_TOKEN_KEY = 'roastnews.refresh_token';

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable: nothing persisted.
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Storage unavailable: nothing to clear.
  }
}

export function getAccessToken(): string | null {
  return safeGet(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return safeGet(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  safeSet(ACCESS_TOKEN_KEY, accessToken);
  safeSet(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  safeRemove(ACCESS_TOKEN_KEY);
  safeRemove(REFRESH_TOKEN_KEY);
}
