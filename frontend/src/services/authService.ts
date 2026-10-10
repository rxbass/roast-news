import type { TokenPair, User } from '../types';
import api, { API_URL, refreshTokens } from './api';

/** sessionStorage key holding where to land after the OAuth round-trip. */
export const RETURN_TO_KEY = 'roastnews.returnTo';

/**
 * Only same-origin relative paths are allowed ("/x", never "//evil.com" or
 * "https://..."), and never the callback page itself. Anything else -> "/".
 */
export function sanitizeReturnTo(value: string | null | undefined): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) {
    return '/';
  }
  if (value.startsWith('/auth/callback')) return '/';
  return value;
}

export function saveReturnTo(path: string): void {
  try {
    window.sessionStorage.setItem(RETURN_TO_KEY, sanitizeReturnTo(path));
  } catch {
    // Storage unavailable: we'll just land on "/".
  }
}

/** Read and remove the stored returnTo (validated). */
export function consumeReturnTo(): string {
  let raw: string | null = null;
  try {
    raw = window.sessionStorage.getItem(RETURN_TO_KEY);
    window.sessionStorage.removeItem(RETURN_TO_KEY);
  } catch {
    raw = null;
  }
  return sanitizeReturnTo(raw);
}

/** sessionStorage key for the per-sign-in nonce (see consumeOAuthNonce). */
export const OAUTH_NONCE_KEY = 'roastnews.oauthNonce';

export function getGoogleSignInUrl(nonce: string): string {
  return `${API_URL}/api/v1/auth/google?nonce=${encodeURIComponent(nonce)}`;
}

/** Read and remove the nonce saved when this tab started signing in. */
export function consumeOAuthNonce(): string | null {
  try {
    const nonce = window.sessionStorage.getItem(OAUTH_NONCE_KEY);
    window.sessionStorage.removeItem(OAUTH_NONCE_KEY);
    return nonce;
  } catch {
    return null;
  }
}

/**
 * Full-page navigation to the backend OAuth start (not an XHR). The nonce comes back with
 * the tokens; the callback page rejects tokens whose nonce doesn't match, so a crafted
 * callback link can't sign this browser into someone else's account.
 */
export function startGoogleSignIn(returnTo: string = '/'): void {
  saveReturnTo(returnTo);
  const nonce = crypto.randomUUID();
  try {
    window.sessionStorage.setItem(OAUTH_NONCE_KEY, nonce);
  } catch {
    // Without storage the callback can't verify the nonce and will show an error.
  }
  window.location.assign(getGoogleSignInUrl(nonce));
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}

/** Rotate tokens. Callers must store the NEW refresh token. */
export function refresh(refreshToken: string): Promise<TokenPair> {
  return refreshTokens(refreshToken);
}

export async function logout(refreshToken: string): Promise<void> {
  await api.post('/auth/logout', { refresh_token: refreshToken });
}
