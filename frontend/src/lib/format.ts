/** Small display formatters shared by the roast UI. */

const DIVISIONS: { amount: number; unit: Intl.RelativeTimeFormatUnit }[] = [
  { amount: 60, unit: 'second' },
  { amount: 60, unit: 'minute' },
  { amount: 24, unit: 'hour' },
  { amount: 7, unit: 'day' },
  { amount: 4.34524, unit: 'week' },
  { amount: 12, unit: 'month' },
  { amount: Number.POSITIVE_INFINITY, unit: 'year' },
];

function toDate(iso: string): Date | null {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "5 minutes ago", "yesterday", ... Falls back to the raw string if unparsable. */
export function formatRelativeTime(iso: string, now: number = Date.now()): string {
  const date = toDate(iso);
  if (!date) return iso;
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  let duration = (date.getTime() - now) / 1000;
  for (const division of DIVISIONS) {
    if (Math.abs(duration) < division.amount) {
      return formatter.format(Math.round(duration), division.unit);
    }
    duration /= division.amount;
  }
  return formatter.format(Math.round(duration), 'year');
}

/** "10 Oct 2026, 2:30 pm" style absolute date. */
export function formatDateTime(iso: string): string {
  const date = toDate(iso);
  if (!date) return iso;
  return date.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}
