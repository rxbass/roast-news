import { Box, Image, Link, Text, VStack } from '@chakra-ui/react';
import { useState } from 'react';

import type { RoastGif } from '../../types/roast';

/** The roast's reaction GIF, credited to GIPHY (required by GIPHY's terms). Hidden if it fails. */
export function RoastGifBox({ gif }: { gif: RoastGif }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;

  return (
    <VStack spacing={1} align="center" data-testid="roast-gif">
      <Box borderRadius="xl" overflow="hidden" boxShadow="md" maxW="full">
        <Image
          src={gif.url}
          alt="Reaction GIF"
          maxH={{ base: '180px', md: '220px' }}
          objectFit="contain"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      </Box>
      <Text fontSize="2xs" color="gray.500">
        <Link href={gif.page_url} target="_blank" rel="noopener noreferrer nofollow">
          Powered by GIPHY
        </Link>
      </Text>
    </VStack>
  );
}

export default RoastGifBox;
