import { Box, Button, Heading, HStack, Link, Text, VStack } from '@chakra-ui/react';
import { useState } from 'react';
import { FiLink, FiRefreshCw } from 'react-icons/fi';
import { Link as RouterLink } from 'react-router-dom';

import { RoastCard, RoastErrorCard, RoastForm, RoastLoading, SignInHint } from '../components/roast';
import { GlassCard, MeshBackground, PageWrapper } from '../components/ui';
import { useCreateRoast } from '../hooks/useRoast';
import { useRoastCooldown } from '../hooks/useRoastCooldown';
import { getErrorInfo } from '../services/api';
import type { RoastCreate } from '../types/roast';

/** Fallback cooldown when a 429 response has no Retry-After header. */
const DEFAULT_RETRY_SECONDS = 60;

export function HomePage() {
  const createRoast = useCreateRoast();
  const cooldown = useRoastCooldown();
  const [formKey, setFormKey] = useState(0);

  const submit = (payload: RoastCreate) => {
    createRoast.mutate(payload, {
      onError: (err) => {
        const info = getErrorInfo(err);
        if (info.status === 429) cooldown.start(info.retryAfter ?? DEFAULT_RETRY_SECONDS);
      },
    });
  };

  const retry = () => {
    if (createRoast.variables) submit(createRoast.variables);
  };

  const roastAnother = () => {
    createRoast.reset();
    setFormKey((k) => k + 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const roast = createRoast.data;
  const errorInfo = createRoast.isError ? getErrorInfo(createRoast.error) : null;

  return (
    <PageWrapper>
      <MeshBackground />
      <VStack spacing={{ base: 6, md: 8 }} textAlign="center" py={{ base: 4, md: 10 }} w="full">
        <VStack spacing={3} px={2}>
          <Heading as="h1" size={{ base: 'xl', md: '3xl' }} lineHeight="short">
            <Box as="span" bgGradient="linear(to-r, brand.500, chili.500)" bgClip="text">
              Roast News
            </Box>{' '}
            <span aria-hidden="true">🌶</span>
          </Heading>
          <Text fontSize={{ base: 'md', md: 'xl' }} maxW="xl" color="gray.600" _dark={{ color: 'gray.300' }}>
            Paste any news link. Get it roasted in Tanglish.
          </Text>
        </VStack>

        <GlassCard w="full" maxW="xl" hoverable={false} p={{ base: 4, md: 6 }} textAlign="left">
          <RoastForm
            key={formKey}
            onSubmit={submit}
            isSubmitting={createRoast.isPending}
            cooldownSeconds={cooldown.secondsLeft}
          />
        </GlassCard>

        <SignInHint />

        <Box w="full" maxW="xl" aria-live="polite">
          {createRoast.isPending && <RoastLoading />}

          {errorInfo && (
            <RoastErrorCard
              error={errorInfo}
              cooldownSeconds={cooldown.secondsLeft}
              onRetry={errorInfo.status === 400 || errorInfo.status === 422 ? undefined : retry}
            />
          )}

          {roast && (
            <VStack spacing={4} align="stretch">
              <RoastCard roast={roast} />
              <HStack justify="space-between" flexWrap="wrap" spacing={3}>
                {roast.status === 'completed' ? (
                  <Link
                    as={RouterLink}
                    to={`/roast/${roast.id}`}
                    display="inline-flex"
                    alignItems="center"
                    gap={1}
                    fontWeight="semibold"
                    color="brand.600"
                  >
                    <FiLink aria-hidden="true" /> Permalink
                  </Link>
                ) : (
                  <Box />
                )}
                <Button
                  size="sm"
                  variant="outline"
                  leftIcon={<FiRefreshCw aria-hidden="true" />}
                  onClick={roastAnother}
                >
                  Roast another one
                </Button>
              </HStack>
            </VStack>
          )}
        </Box>
      </VStack>
    </PageWrapper>
  );
}

export default HomePage;
