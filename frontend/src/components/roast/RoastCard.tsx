import {
  Badge,
  Box,
  Divider,
  Heading,
  HStack,
  Link,
  Text,
  useColorModeValue,
  VStack,
  Wrap,
} from '@chakra-ui/react';

import { formatDateTime } from '../../lib/format';
import { MotionBox } from '../../lib/motion';
import type { Roast } from '../../types/roast';
import { SpiceBadge } from './RoastBadges';
import { RoastRefusedCard } from './RoastRefusedCard';
import { ShareButtons } from './ShareButtons';

export interface RoastCardProps {
  roast: Roast;
  showShare?: boolean;
}

/**
 * Completed roast with a reveal animation. Refused/failed roasts render the
 * soft refusal card instead (no share buttons). The roast text is rendered
 * as plain text only, never as HTML.
 */
export function RoastCard({ roast, showShare = true }: RoastCardProps) {
  const bg = useColorModeValue('whiteAlpha.800', 'whiteAlpha.100');
  const borderColor = useColorModeValue('brand.100', 'whiteAlpha.200');
  const quoteBg = useColorModeValue('orange.50', 'whiteAlpha.50');

  if (roast.status !== 'completed' || !roast.roast_text) {
    return <RoastRefusedCard roast={roast} />;
  }

  return (
    <MotionBox
      w="full"
      p={{ base: 4, md: 6 }}
      borderRadius="2xl"
      borderWidth="1px"
      borderColor={borderColor}
      bg={bg}
      backdropFilter="blur(16px)"
      boxShadow="xl"
      textAlign="left"
      initial={{ opacity: 0, y: 30, scale: 0.95, rotate: -1 }}
      animate={{
        opacity: 1,
        y: 0,
        scale: 1,
        rotate: 0,
        transition: { type: 'spring', stiffness: 220, damping: 18 },
      }}
      data-testid="roast-card"
    >
      <VStack align="stretch" spacing={4}>
        <Wrap spacing={2} align="center">
          <SpiceBadge level={roast.spice_level} />
          <Badge variant="subtle" colorScheme={roast.cached ? 'purple' : 'green'} borderRadius="full" px={2}>
            {roast.cached ? 'Already roasted 🔁' : 'Fresh from the oven'}
          </Badge>
        </Wrap>

        <Box minW={0}>
          <Heading
            as="h2"
            size="sm"
            fontFamily="body"
            lineHeight="short"
            noOfLines={2}
            wordBreak="break-word"
          >
            <Link
              href={roast.source_url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              _hover={{ color: 'brand.500', textDecoration: 'underline' }}
            >
              {roast.article_title || roast.source_domain}
            </Link>
          </Heading>
          <HStack spacing={2} fontSize="xs" color="gray.500" mt={1} flexWrap="wrap">
            <Text>{roast.source_domain}</Text>
            <Text aria-hidden="true">•</Text>
            <Text as="time" dateTime={roast.created_at}>
              {formatDateTime(roast.created_at)}
            </Text>
          </HStack>
        </Box>

        <Box
          bg={quoteBg}
          borderLeftWidth="4px"
          borderLeftColor="brand.500"
          borderRadius="lg"
          p={{ base: 3, md: 4 }}
        >
          <Text
            whiteSpace="pre-line"
            fontSize={{ base: 'md', md: 'lg' }}
            lineHeight="tall"
            wordBreak="break-word"
            data-testid="roast-text"
          >
            {roast.roast_text}
          </Text>
        </Box>

        {showShare && (
          <>
            <Divider />
            <ShareButtons
              roastId={roast.id}
              roastText={roast.roast_text}
              articleTitle={roast.article_title}
            />
          </>
        )}
      </VStack>
    </MotionBox>
  );
}

export default RoastCard;
