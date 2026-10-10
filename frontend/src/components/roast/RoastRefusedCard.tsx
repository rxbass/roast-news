import { Heading, HStack, Text, useColorModeValue, VStack } from '@chakra-ui/react';

import { MotionBox } from '../../lib/motion';
import type { Roast } from '../../types/roast';

const FALLBACK_REFUSED = 'Indha news-a roast panna manasu varala machan. Vera link try pannu! 🙏';
const FALLBACK_FAILED = 'Roast oven konjam burn aagiduchu. Try again in a bit! 😅';

/** Soft (yellow/orange) card for refused or failed roasts. Never shows share buttons. */
export function RoastRefusedCard({ roast }: { roast: Roast }) {
  const bg = useColorModeValue('orange.50', 'whiteAlpha.100');
  const borderColor = useColorModeValue('turmeric.300', 'turmeric.600');
  const isFailed = roast.status === 'failed';

  return (
    <MotionBox
      w="full"
      p={{ base: 5, md: 6 }}
      borderRadius="2xl"
      borderWidth="2px"
      borderColor={borderColor}
      bg={bg}
      textAlign="left"
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1, transition: { duration: 0.3 } }}
      data-testid="roast-refused"
    >
      <VStack align="stretch" spacing={3}>
        <HStack spacing={2}>
          <Text fontSize="2xl" aria-hidden="true">
            {isFailed ? '😵' : '🙏'}
          </Text>
          <Heading as="h2" size="sm" fontFamily="body">
            {isFailed ? 'Roast fail aagiduchu' : 'Indha news-ku roast illa'}
          </Heading>
        </HStack>
        <Text whiteSpace="pre-line" wordBreak="break-word">
          {roast.message?.trim() || (isFailed ? FALLBACK_FAILED : FALLBACK_REFUSED)}
        </Text>
        {/* Only the domain: a refused page's title/link is attacker-controlled text we
            must not republish on our own permalink. */}
        {roast.source_domain && (
          <Text fontSize="sm" color="gray.500" wordBreak="break-word">
            Source: {roast.source_domain}
          </Text>
        )}
      </VStack>
    </MotionBox>
  );
}

export default RoastRefusedCard;
