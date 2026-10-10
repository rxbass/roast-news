import { Button, Heading, HStack, Text, useColorModeValue, VStack } from '@chakra-ui/react';

import { MotionBox } from '../../lib/motion';
import type { ErrorInfo } from '../../services/api';
import { getRoastErrorCopy } from './errorCopy';

export interface RoastErrorCardProps {
  error: ErrorInfo;
  /** Live seconds left for a 429 cooldown (0 when done). */
  cooldownSeconds?: number;
  onRetry?: () => void;
  retryLabel?: string;
}

export function RoastErrorCard({
  error,
  cooldownSeconds = 0,
  onRetry,
  retryLabel = 'Try again',
}: RoastErrorCardProps) {
  const copy = getRoastErrorCopy(error);
  const bg = useColorModeValue('chili.50', 'whiteAlpha.100');
  const borderColor = useColorModeValue('chili.200', 'chili.700');
  const isRateLimited = error.status === 429;
  const waiting = isRateLimited && cooldownSeconds > 0;

  return (
    <MotionBox
      w="full"
      p={{ base: 5, md: 6 }}
      borderRadius="2xl"
      borderWidth="2px"
      borderColor={borderColor}
      bg={bg}
      textAlign="left"
      role="alert"
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: [-12, 8, -4, 0], transition: { duration: 0.4 } }}
      data-testid="roast-error"
    >
      <VStack align="stretch" spacing={3}>
        <HStack spacing={2}>
          <Text fontSize="2xl" aria-hidden="true">
            {copy.emoji}
          </Text>
          <Heading as="h2" size="sm" fontFamily="body">
            {copy.title}
          </Heading>
        </HStack>
        <Text wordBreak="break-word">{copy.description}</Text>
        {isRateLimited && (
          <Text fontWeight="semibold" aria-live="polite" data-testid="cooldown">
            {waiting ? `Try again in ${cooldownSeconds}s ⏳` : 'Ready! Ippo try pannu 🔥'}
          </Text>
        )}
        {onRetry && (
          <HStack>
            <Button size="sm" variant="outline" onClick={onRetry} isDisabled={waiting}>
              {retryLabel}
            </Button>
          </HStack>
        )}
      </VStack>
    </MotionBox>
  );
}

export default RoastErrorCard;
