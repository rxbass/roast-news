import { HStack, Spinner, Text, VStack } from '@chakra-ui/react';
import { AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';

import { MotionBox } from '../../lib/motion';
import { GlassCard } from '../ui';
import { LOADING_INTERVAL_MS, LOADING_LINES } from './loadingLines';

export function RoastLoading() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % LOADING_LINES.length);
    }, LOADING_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <GlassCard hoverable={false} w="full" role="status" aria-live="polite">
      <VStack spacing={4} py={2}>
        <MotionBox
          fontSize="4xl"
          aria-hidden="true"
          animate={{
            rotate: [0, -10, 10, 0],
            scale: [1, 1.15, 1],
            transition: { duration: 1.2, repeat: Infinity },
          }}
        >
          🔥
        </MotionBox>
        <HStack spacing={3} minH="8">
          <Spinner size="sm" color="brand.500" />
          <AnimatePresence mode="wait">
            <MotionBox
              key={index}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0, transition: { duration: 0.25 } }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.2 } }}
            >
              <Text fontWeight="semibold">{LOADING_LINES[index]}</Text>
            </MotionBox>
          </AnimatePresence>
        </HStack>
      </VStack>
    </GlassCard>
  );
}

export default RoastLoading;
