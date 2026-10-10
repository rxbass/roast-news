import { AspectRatio, Box, Image, type AspectRatioProps } from '@chakra-ui/react';
import { useState } from 'react';

export interface MoviePosterProps extends Omit<AspectRatioProps, 'children' | 'ratio'> {
  url: string | null;
  title: string;
}

/** TMDB poster (2:3) with a clapperboard fallback when there's no image or it fails to load. */
export function MoviePoster({ url, title, w = '48px', ...rest }: MoviePosterProps) {
  const [failed, setFailed] = useState(false);
  return (
    <AspectRatio
      ratio={2 / 3}
      w={w}
      flexShrink={0}
      borderRadius="md"
      overflow="hidden"
      bg="blackAlpha.100"
      _dark={{ bg: 'whiteAlpha.100' }}
      {...rest}
    >
      {url && !failed ? (
        <Image
          src={url}
          alt={`${title} poster`}
          objectFit="cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <Box as="span" fontSize="xl" aria-hidden="true" data-testid="poster-fallback">
          🎬
        </Box>
      )}
    </AspectRatio>
  );
}

export default MoviePoster;
