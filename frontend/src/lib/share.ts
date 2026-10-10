/**
 * Pure share-URL builders for roasts. No DOM access except the optional
 * `window.location.origin` default in `buildPermalink`.
 */

/** Maximum length of a post on X (Twitter). */
export const X_MAX_LENGTH = 280;

const ELLIPSIS = '…';
const SEPARATOR = '\n\n';

/** Absolute permalink for a roast, e.g. https://movieroast.live/roast/<id>. */
export function buildPermalink(id: string, origin: string = window.location.origin): string {
  return `${origin.replace(/\/+$/, '')}/roast/${encodeURIComponent(id)}`;
}

/** Full share text: the roast, a blank line, then the permalink. */
export function buildShareText(roastText: string, permalink: string): string {
  const text = roastText.trim();
  return text ? `${text}${SEPARATOR}${permalink}` : permalink;
}

/** Length in Unicode code points (so emoji are not split in half). */
function codePointLength(value: string): number {
  return Array.from(value).length;
}

/**
 * Truncate `text` to at most `max` code points, appending "…" when cut.
 * Trailing whitespace before the ellipsis is trimmed.
 */
export function truncateText(text: string, max: number): string {
  if (max <= 0) return '';
  const chars = Array.from(text);
  if (chars.length <= max) return text;
  if (max === 1) return ELLIPSIS;
  return `${chars
    .slice(0, max - 1)
    .join('')
    .trimEnd()}${ELLIPSIS}`;
}

/**
 * Text for an X post: the roast (truncated with "…" if needed) plus the
 * permalink, never longer than 280 characters in total.
 */
export function buildXText(roastText: string, permalink: string): string {
  const budget = X_MAX_LENGTH - codePointLength(permalink) - SEPARATOR.length;
  const text = roastText.trim();
  if (budget <= 0 || !text) return truncateText(permalink, X_MAX_LENGTH);
  return `${truncateText(text, budget)}${SEPARATOR}${permalink}`;
}

/** https://wa.me/?text=<roast + permalink> */
export function buildWhatsAppUrl(roastText: string, permalink: string): string {
  return `https://wa.me/?text=${encodeURIComponent(buildShareText(roastText, permalink))}`;
}

/** https://twitter.com/intent/tweet?text=<short roast + permalink> */
export function buildXUrl(roastText: string, permalink: string): string {
  return `https://twitter.com/intent/tweet?text=${encodeURIComponent(buildXText(roastText, permalink))}`;
}
