import type { ErrorInfo } from '../../services/api';

export interface RoastErrorCopy {
  title: string;
  description: string;
  emoji: string;
}

/** Map an API error to friendly Tanglish copy. Prefers the server's `message`. */
export function getRoastErrorCopy(error: ErrorInfo): RoastErrorCopy {
  const server = error.message?.trim() || null;
  switch (error.status) {
    case 400:
      return {
        emoji: '🙅',
        title: 'Indha link sari illa machan',
        description: server ?? 'That link looks invalid or blocked. Try a public news article URL.',
      };
    case 401:
      return {
        emoji: '🔑',
        title: 'Session mudinjiduchu',
        description: server ?? 'Your session expired. Sign in again to continue.',
      };
    case 404:
      return {
        emoji: '🔍',
        title: 'Thedi thedi paathen, kaanom!',
        description: server ?? "We couldn't find that roast.",
      };
    case 422:
      return {
        emoji: '📰',
        title: 'Article-ae kaanom!',
        description:
          server ?? "We couldn't read a proper article on that page. Try a direct news story link.",
      };
    case 429:
      return {
        emoji: '⏳',
        title: 'Konjam slow-a po machan!',
        description: server ?? 'Too many roasts in a short time. Take a chai break.',
      };
    case 502:
    case 503:
    case 504:
      return {
        emoji: '😴',
        title: 'Server konjam tired, try again',
        description: server ?? 'The roast kitchen is overloaded right now. Try again in a bit.',
      };
    case null:
      return {
        emoji: '📡',
        title: 'Network-ae illa machan',
        description: server ?? "Couldn't reach the server. Check your connection and try again.",
      };
    default:
      return {
        emoji: '😵',
        title: 'Ayyo, edho thappu nadandhuduchu',
        description: server ?? 'Something went wrong. Please try again.',
      };
  }
}
