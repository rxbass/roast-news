import { describe, expect, it } from 'vitest';

import {
  buildPermalink,
  buildShareText,
  buildWhatsAppUrl,
  buildXText,
  buildXUrl,
  truncateText,
  X_MAX_LENGTH,
} from '../../lib/share';

const PERMALINK = 'https://roast.news/roast/abc-123';

function decodeParam(url: string, prefix: string): string {
  expect(url.startsWith(prefix)).toBe(true);
  return decodeURIComponent(url.slice(prefix.length));
}

describe('share URL builders', () => {
  it('builds a permalink from origin and id', () => {
    expect(buildPermalink('abc-123', 'https://roast.news')).toBe(PERMALINK);
    expect(buildPermalink('abc-123', 'https://roast.news/')).toBe(PERMALINK);
  });

  it('defaults the permalink origin to window.location.origin', () => {
    expect(buildPermalink('x')).toBe(`${window.location.origin}/roast/x`);
  });

  it('joins roast text and permalink with a blank line', () => {
    expect(buildShareText('  Semma roast  ', PERMALINK)).toBe(`Semma roast\n\n${PERMALINK}`);
  });

  it('encodes the WhatsApp text (newlines, &, #, emoji)', () => {
    const text = 'Line 1 & #2\nAyyo 😂?';
    const url = buildWhatsAppUrl(text, PERMALINK);
    expect(url).not.toContain(' ');
    expect(url).not.toContain('#');
    expect(url.split('&')).toHaveLength(1);
    expect(url).not.toContain('\n');
    expect(decodeParam(url, 'https://wa.me/?text=')).toBe(`${text}\n\n${PERMALINK}`);
  });

  it('keeps a short X post intact', () => {
    const url = buildXUrl('Short roast', PERMALINK);
    expect(decodeParam(url, 'https://twitter.com/intent/tweet?text=')).toBe(`Short roast\n\n${PERMALINK}`);
  });

  it('truncates long X posts to at most 280 characters with an ellipsis', () => {
    const longText = 'Vera level mokka news 🌶 '.repeat(40);
    const text = buildXText(longText, PERMALINK);
    expect(Array.from(text).length).toBeLessThanOrEqual(X_MAX_LENGTH);
    expect(text.endsWith(`…\n\n${PERMALINK}`)).toBe(true);

    const decoded = decodeParam(buildXUrl(longText, PERMALINK), 'https://twitter.com/intent/tweet?text=');
    expect(Array.from(decoded).length).toBeLessThanOrEqual(X_MAX_LENGTH);
    expect(decoded).toContain(PERMALINK);
  });

  it('never splits an emoji when truncating', () => {
    const result = truncateText('😂😂😂😂😂', 3);
    expect(result).toBe('😂😂…');
    expect(truncateText('abc', 5)).toBe('abc');
  });
});
