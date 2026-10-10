import { Heading, Text, VStack } from '@chakra-ui/react';
import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { movieLabel } from '../components/movie';
import { RoastCard, RoastCardSkeleton, RoastErrorCard } from '../components/roast';
import { GlassCard, GradientButton, PageWrapper } from '../components/ui';
import { useRoast } from '../hooks/useRoast';
import { getErrorInfo } from '../services/api';

export function RoastPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: roast, error, isPending, isError, refetch } = useRoast(id);

  const title = roast ? movieLabel(roast.movie) : undefined;
  useEffect(() => {
    if (!title) return undefined;
    const previous = document.title;
    document.title = `${title} roast | Movie Roast 🎬`;
    return () => {
      document.title = previous;
    };
  }, [title]);

  const goHome = () => navigate('/');
  const errorInfo = isError ? getErrorInfo(error) : null;
  const notFound = !id || errorInfo?.status === 404;

  return (
    <PageWrapper>
      <VStack spacing={6} w="full" maxW="2xl" mx="auto" py={{ base: 2, md: 6 }}>
        {notFound ? (
          <GlassCard w="full" textAlign="center" hoverable={false} data-testid="roast-not-found">
            <VStack spacing={4}>
              <Text fontSize="5xl" aria-hidden="true">
                🔍
              </Text>
              <Heading as="h1" size="md">
                Thedi thedi paathen, kaanom!
              </Heading>
              <Text>This roast doesn&apos;t exist or was deleted.</Text>
              <GradientButton onClick={goHome}>Roast your own 🔥</GradientButton>
            </VStack>
          </GlassCard>
        ) : errorInfo ? (
          <RoastErrorCard error={errorInfo} onRetry={() => void refetch()} />
        ) : isPending || !roast ? (
          <RoastCardSkeleton />
        ) : (
          <>
            <RoastCard roast={roast} />
            <GradientButton onClick={goHome} w={{ base: 'full', sm: 'auto' }}>
              Roast another movie →
            </GradientButton>
          </>
        )}
      </VStack>
    </PageWrapper>
  );
}

export default RoastPage;
