import { Box, Skeleton, SkeletonText, Stack, useColorModeValue } from '@chakra-ui/react';

export function RoastCardSkeleton() {
  const bg = useColorModeValue('whiteAlpha.800', 'whiteAlpha.100');
  return (
    <Box
      w="full"
      p={{ base: 4, md: 6 }}
      borderRadius="2xl"
      bg={bg}
      boxShadow="md"
      aria-busy="true"
      aria-label="Loading roast"
    >
      <Stack spacing={4}>
        <Skeleton h="5" w="40%" borderRadius="full" />
        <Skeleton h="6" w="85%" />
        <SkeletonText noOfLines={5} spacing={3} skeletonHeight="3" />
      </Stack>
    </Box>
  );
}

export function RoastListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <Stack spacing={4} aria-busy="true" aria-label="Loading roasts">
      {Array.from({ length: count }, (_, i) => (
        <Box key={i} p={4} borderRadius="xl" borderWidth="1px">
          <Skeleton h="4" w="70%" mb={2} />
          <Skeleton h="3" w="40%" mb={3} />
          <Skeleton h="4" w="30%" borderRadius="full" />
        </Box>
      ))}
    </Stack>
  );
}
