export const MAX_URL_LENGTH = 2048;

/**
 * Client-side check for the news URL. Returns an error message, or null when
 * the URL looks fine. The backend still does the real (SSRF-safe) validation.
 */
export function validateNewsUrl(raw: string): string | null {
  const value = raw.trim();
  if (!value) return 'News link podu machan — URL is required.';
  if (value.length > MAX_URL_LENGTH) return `Romba neelam! URL must be at most ${MAX_URL_LENGTH} characters.`;
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return 'Idhu URL-ae illa. Paste a full link starting with http:// or https://';
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return 'Only http:// or https:// links work machan.';
  }
  if (!parsed.hostname || !parsed.hostname.includes('.')) {
    return 'Idhu URL-ae illa. Paste a full link starting with http:// or https://';
  }
  return null;
}
