import { Heading, Spinner, Text, VStack } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';
import { GlassCard, PageWrapper } from '../ui';
import { GoogleSignInButton } from './GoogleSignInButton';

export interface ProtectedRouteProps {
  children: ReactNode;
}

/**
 * Renders children only for signed-in users. There's no login page in this
 * app, so logged-out users get an inline sign-in prompt instead of a redirect.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isLoading, isAuthenticated } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <VStack py={16}>
        <Spinner size="lg" color="brand.500" aria-label="Checking your session" />
      </VStack>
    );
  }

  if (!isAuthenticated) {
    const returnTo = `${location.pathname}${location.search}`;
    return (
      <PageWrapper>
        <VStack py={{ base: 8, md: 16 }}>
          <GlassCard w="full" maxW="md" textAlign="center" hoverable={false}>
            <VStack spacing={4}>
              <Heading as="h1" size="lg">
                Login venum 🔐
              </Heading>
              <Text>My Roasts paakka login pannunga machan</Text>
              <GoogleSignInButton returnTo={returnTo} />
            </VStack>
          </GlassCard>
        </VStack>
      </PageWrapper>
    );
  }

  return <>{children}</>;
}

export default ProtectedRoute;
