import { Box, useColorModeValue } from '@chakra-ui/react';

import { MotionBox } from '../../lib/motion';

const pulse = {
  opacity: [0.25, 0.4, 0.25],
  scale: [1, 1.08, 1],
  transition: { duration: 6, repeat: Infinity, ease: 'easeInOut' },
};

/** Fixed, decorative gradient-mesh backdrop for landing/auth pages. */
export function MeshBackground() {
  const base = useColorModeValue(
    'linear(to-br, orange.50, white, red.50)',
    'linear(to-br, gray.900, gray.800, red.900)',
  );
  const blobA = useColorModeValue('brand.200', 'brand.700');
  const blobB = useColorModeValue('chili.200', 'chili.800');
  const blobC = useColorModeValue('turmeric.200', 'turmeric.800');

  return (
    <Box position="fixed" inset={0} zIndex={-1} overflow="hidden" aria-hidden="true" pointerEvents="none">
      <Box position="absolute" inset={0} bgGradient={base} />
      <MotionBox
        position="absolute"
        top="-10%"
        left="20%"
        w={{ base: '64', md: '96' }}
        h={{ base: '64', md: '96' }}
        bg={blobA}
        borderRadius="full"
        filter="blur(64px)"
        animate={pulse}
      />
      <MotionBox
        position="absolute"
        bottom="-10%"
        right="20%"
        w={{ base: '64', md: '96' }}
        h={{ base: '64', md: '96' }}
        bg={blobB}
        borderRadius="full"
        filter="blur(64px)"
        animate={{ ...pulse, transition: { ...pulse.transition, delay: 2 } }}
      />
      <MotionBox
        position="absolute"
        top="40%"
        left="-5%"
        w={{ base: '48', md: '72' }}
        h={{ base: '48', md: '72' }}
        bg={blobC}
        borderRadius="full"
        filter="blur(64px)"
        animate={{ ...pulse, transition: { ...pulse.transition, delay: 4 } }}
      />
    </Box>
  );
}

export default MeshBackground;
