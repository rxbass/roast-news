import { Badge, type BadgeProps } from '@chakra-ui/react';

import type { RoastStatus, SpiceLevel } from '../../types/roast';
import { getSpiceOption, STATUS_META } from './spice';

export function SpiceBadge({ level, ...rest }: { level: SpiceLevel } & BadgeProps) {
  const option = getSpiceOption(level);
  return (
    <Badge colorScheme={option.colorScheme} variant="subtle" borderRadius="full" px={2} {...rest}>
      <span aria-hidden="true">{option.emoji} </span>
      {option.label}
    </Badge>
  );
}

export function StatusBadge({ status, ...rest }: { status: RoastStatus } & BadgeProps) {
  const meta = STATUS_META[status];
  return (
    <Badge colorScheme={meta.colorScheme} variant="outline" borderRadius="full" px={2} {...rest}>
      {meta.label}
    </Badge>
  );
}
