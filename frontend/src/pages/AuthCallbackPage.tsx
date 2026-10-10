import { Heading, Spinner, Text, VStack, useToast } from '@chakra-ui/react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { GlassCard, GradientButton, PageWrapper } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { consumeOAuthNonce, consumeReturnTo } from '../services/authService';

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: 'Login cancel pannitinga, paravala! Roast pannradhuku login thevai illa.',
  state_mismatch: 'Session confuse aayiduchu. Oru thadava thirumba try pannunga.',
  email_unverified: 'Unga Google email verify aagala machan. Verify panni vaanga!',
  account_disabled: 'Indha account disable pannirukom. Sorry machan.',
  oauth_failed: 'Google kitta pesa mudiyala. Konjam neram kazhichu try pannunga.',
  sign_in_failed: 'Login aagala machan. Thirumba try pannunga.',
};

function errorMessageFor(code: string): string {
  return ERROR_MESSAGES[code] ?? ERROR_MESSAGES.oauth_failed;
}

function firstName(fullName: string | null, email: string): string {
  const name = fullName?.trim();
  if (name) return name.split(/\s+/)[0];
  return email.split('@')[0];
}

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { completeSignIn } = useAuth();
  const [errorCode, setErrorCode] = useState<string | null>(null);
  // StrictMode runs effects twice; the hash is consumed on the first run.
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    // Never leave tokens sitting in the URL / history.
    window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);

    const error = params.get('error');
    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');

    const expectedNonce = consumeOAuthNonce();

    if (error || !accessToken || !refreshToken) {
      setErrorCode(error ?? 'oauth_failed');
      return;
    }
    // Only accept tokens from a sign-in this tab started (blocks crafted callback links).
    if (!expectedNonce || params.get('nonce') !== expectedNonce) {
      setErrorCode('state_mismatch');
      return;
    }

    completeSignIn({
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: params.get('token_type') ?? 'bearer',
    })
      .then((user) => {
        toast({
          title: `Vanakkam, ${firstName(user.full_name, user.email)}! 🌶`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        navigate(consumeReturnTo(), { replace: true });
      })
      .catch(() => {
        setErrorCode('sign_in_failed');
      });
  }, [completeSignIn, navigate, toast]);

  if (errorCode) {
    return (
      <PageWrapper>
        <VStack py={{ base: 8, md: 16 }}>
          <GlassCard w="full" maxW="md" textAlign="center" hoverable={false} role="alert">
            <VStack spacing={4}>
              <Heading as="h1" size="lg">
                Aiyo! Login aagala 😅
              </Heading>
              <Text>{errorMessageFor(errorCode)}</Text>
              <GradientButton onClick={() => navigate('/', { replace: true })}>Back to home</GradientButton>
            </VStack>
          </GlassCard>
        </VStack>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper>
      <VStack spacing={4} py={16}>
        <Spinner size="lg" color="brand.500" />
        <Text>Signing you in...</Text>
      </VStack>
    </PageWrapper>
  );
}

export default AuthCallbackPage;
