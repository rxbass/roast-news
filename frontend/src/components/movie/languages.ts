/** Display names for the TMDB `original_language` codes users will see most. */
const LANGUAGE_NAMES: Record<string, string> = {
  ta: 'Tamil',
  te: 'Telugu',
  ml: 'Malayalam',
  kn: 'Kannada',
  hi: 'Hindi',
  en: 'English',
  ko: 'Korean',
  ja: 'Japanese',
  fr: 'French',
  es: 'Spanish',
};

export function languageName(code: string): string {
  return LANGUAGE_NAMES[code] ?? code.toUpperCase();
}

/** "Leo (2023)" or just "Leo" when the year is unknown. */
export function movieLabel(movie: { title: string; year: number | null }): string {
  return movie.year ? `${movie.title} (${movie.year})` : movie.title;
}
