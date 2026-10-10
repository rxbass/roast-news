import { Heading, Text, VStack } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';

import { GlassCard, GradientButton, PageWrapper } from '../components/ui';

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <PageWrapper>
      <VStack py={{ base: 8, md: 16 }}>
        <GlassCard w="full" maxW="md" textAlign="center">
          <VStack spacing={4}>
            <Heading as="h1" size="2xl">
              404
            </Heading>
            <Text>Aiyo! Indha page-a kaanom. This page doesn&apos;t exist.</Text>
            <GradientButton onClick={() => navigate('/')}>Back to home</GradientButton>
          </VStack>
        </GlassCard>
      </VStack>
    </PageWrapper>
  );
}

export default NotFoundPage;
