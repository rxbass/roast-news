import type { RoastStatus, SpiceLevel } from '../../types/roast';

export interface SpiceOption {
  value: SpiceLevel;
  emoji: string;
  label: string;
  tagline: string;
  colorScheme: string;
}

export const SPICE_OPTIONS: readonly SpiceOption[] = [
  { value: 'mild', emoji: '🌶', label: 'Mild', tagline: 'Light-a teasing', colorScheme: 'turmeric' },
  { value: 'medium', emoji: '🌶🌶', label: 'Medium', tagline: 'Sarcasm overload', colorScheme: 'brand' },
  {
    value: 'extra_spicy',
    emoji: '🌶🌶🌶',
    label: 'Extra Spicy',
    tagline: 'No mercy machan',
    colorScheme: 'chili',
  },
];

export const DEFAULT_SPICE: SpiceLevel = 'medium';

export function getSpiceOption(level: SpiceLevel): SpiceOption {
  return SPICE_OPTIONS.find((o) => o.value === level) ?? SPICE_OPTIONS[1];
}

export function isSpiceLevel(value: string): value is SpiceLevel {
  return SPICE_OPTIONS.some((o) => o.value === value);
}

export const STATUS_META: Record<RoastStatus, { label: string; colorScheme: string }> = {
  completed: { label: 'Roasted', colorScheme: 'green' },
  refused: { label: 'Skipped', colorScheme: 'yellow' },
  failed: { label: 'Failed', colorScheme: 'red' },
};
