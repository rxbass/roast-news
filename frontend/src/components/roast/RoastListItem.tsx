import {
  Box,
  Flex,
  HStack,
  IconButton,
  LinkBox,
  LinkOverlay,
  Text,
  Tooltip,
  useColorModeValue,
  Wrap,
} from '@chakra-ui/react';
import { FiTrash2 } from 'react-icons/fi';
import { Link as RouterLink } from 'react-router-dom';

import { formatDateTime, formatRelativeTime } from '../../lib/format';
import type { Roast } from '../../types/roast';
import { languageName, MoviePoster, movieLabel } from '../movie';
import { SpiceBadge, StatusBadge } from './RoastBadges';

export interface RoastListItemProps {
  roast: Roast;
  onDelete: (roast: Roast) => void;
  isDeleting?: boolean;
}

export function RoastListItem({ roast, onDelete, isDeleting = false }: RoastListItemProps) {
  const bg = useColorModeValue('whiteAlpha.800', 'whiteAlpha.100');
  const borderColor = useColorModeValue('gray.100', 'whiteAlpha.200');
  const title = movieLabel(roast.movie);

  return (
    <Flex
      align="flex-start"
      gap={3}
      p={{ base: 3, md: 4 }}
      bg={bg}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius="xl"
      boxShadow="sm"
      _hover={{ boxShadow: 'md' }}
      data-testid="roast-list-item"
    >
      <MoviePoster url={roast.movie.poster_url} title={roast.movie.title} w="44px" />
      <LinkBox flex="1" minW={0}>
        <LinkOverlay as={RouterLink} to={`/roast/${roast.id}`}>
          <Text fontWeight="semibold" noOfLines={2} wordBreak="break-word">
            {title}
          </Text>
        </LinkOverlay>
        <HStack spacing={2} fontSize="xs" color="gray.500" mt={1} flexWrap="wrap">
          <Text noOfLines={1}>{languageName(roast.movie.original_language)}</Text>
          <Text aria-hidden="true">•</Text>
          <Tooltip label={formatDateTime(roast.created_at)} openDelay={400}>
            <Text as="time" dateTime={roast.created_at}>
              {formatRelativeTime(roast.created_at)}
            </Text>
          </Tooltip>
        </HStack>
        <Wrap spacing={2} mt={2}>
          <SpiceBadge level={roast.spice_level} />
          <StatusBadge status={roast.status} />
        </Wrap>
      </LinkBox>
      <Box flexShrink={0}>
        <IconButton
          aria-label={`Delete roast: ${title}`}
          icon={<FiTrash2 />}
          size="sm"
          variant="ghost"
          colorScheme="red"
          isLoading={isDeleting}
          onClick={() => onDelete(roast)}
        />
      </Box>
    </Flex>
  );
}

export default RoastListItem;
