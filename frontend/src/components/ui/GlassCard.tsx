import { useColorModeValue, type BoxProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';

import { MotionBox } from '../../lib/motion';

export interface GlassCardProps extends Omit<BoxProps, 'transition'> {
  children: ReactNode;
  /** Disable the hover lift (e.g. for static content). Defaults to true. */
  hoverable?: boolean;
}

export function GlassCard({ children, hoverable = true, ...rest }: GlassCardProps) {
  const bg = useColorModeValue('whiteAlpha.700', 'whiteAlpha.100');
  const borderColor = useColorModeValue('whiteAlpha.800', 'whiteAlpha.200');

  return (
    <MotionBox
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.35 } }}
      whileHover={hoverable ? { scale: 1.02, y: -5 } : undefined}
      p={6}
      borderRadius="2xl"
      bg={bg}
      backdropFilter="blur(16px)"
      borderWidth="1px"
      borderColor={borderColor}
      boxShadow="xl"
      _hover={hoverable ? { boxShadow: '2xl' } : undefined}
      {...rest}
    >
      {children}
    </MotionBox>
  );
}

export default GlassCard;
