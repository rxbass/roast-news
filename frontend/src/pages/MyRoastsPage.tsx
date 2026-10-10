import { Button, Heading, HStack, Text, useToast, VStack } from '@chakra-ui/react';
import { useState } from 'react';
import { FiChevronLeft, FiChevronRight } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';

import { DeleteRoastDialog, RoastErrorCard, RoastListItem, RoastListSkeleton } from '../components/roast';
import { AnimatedList, GlassCard, GradientButton, PageWrapper } from '../components/ui';
import { useDeleteRoast, useMyRoasts } from '../hooks/useRoast';
import { getErrorInfo } from '../services/api';
import { MY_ROASTS_PAGE_SIZE } from '../services/roastService';
import type { Roast } from '../types/roast';

export function MyRoastsPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [pendingDelete, setPendingDelete] = useState<Roast | null>(null);

  const { data, error, isPending, isError, isFetching, refetch } = useMyRoasts(page, MY_ROASTS_PAGE_SIZE);
  const deleteRoast = useDeleteRoast();

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / MY_ROASTS_PAGE_SIZE));
  const items = data?.items ?? [];

  const confirmDelete = () => {
    if (!pendingDelete) return;
    const target = pendingDelete;
    deleteRoast.mutate(target.id, {
      onSuccess: () => {
        toast({ status: 'success', title: 'Roast deleted. Poyiduchu! 🗑', duration: 2500, isClosable: true });
        setPendingDelete(null);
        // If we just emptied the last page, step back one.
        if (items.length === 1 && page > 1) setPage((p) => p - 1);
      },
      onError: (err) => {
        const info = getErrorInfo(err);
        toast({
          status: 'error',
          title: 'Delete aagala machan',
          description: info.message ?? info.detail,
          duration: 4000,
          isClosable: true,
        });
        setPendingDelete(null);
      },
    });
  };

  const errorInfo = isError ? getErrorInfo(error) : null;

  return (
    <PageWrapper>
      <VStack spacing={6} align="stretch" w="full" maxW="3xl" mx="auto">
        <HStack justify="space-between" flexWrap="wrap" spacing={3}>
          <Heading as="h1" size={{ base: 'md', md: 'lg' }}>
            My Roasts 🌶
          </Heading>
          {total > 0 && (
            <Text fontSize="sm" color="gray.500">
              {total} roast{total === 1 ? '' : 's'}
            </Text>
          )}
        </HStack>

        {errorInfo ? (
          <RoastErrorCard
            error={errorInfo}
            onRetry={errorInfo.status === 401 ? undefined : () => void refetch()}
          />
        ) : isPending ? (
          <RoastListSkeleton />
        ) : items.length === 0 ? (
          <GlassCard hoverable={false} textAlign="center" data-testid="my-roasts-empty">
            <VStack spacing={4}>
              <Text fontSize="5xl" aria-hidden="true">
                🍳
              </Text>
              <Heading as="h2" size="sm" fontFamily="body">
                Innum onnum roast pannala!
              </Heading>
              <Text>You haven&apos;t roasted any news yet. Start with your first one.</Text>
              <GradientButton onClick={() => navigate('/')}>Roast something 🔥</GradientButton>
            </VStack>
          </GlassCard>
        ) : (
          <>
            <AnimatedList key={page}>
              {items.map((roast) => (
                <RoastListItem
                  key={roast.id}
                  roast={roast}
                  onDelete={setPendingDelete}
                  isDeleting={deleteRoast.isPending && deleteRoast.variables === roast.id}
                />
              ))}
            </AnimatedList>

            {totalPages > 1 && (
              <HStack justify="space-between" as="nav" aria-label="Pagination">
                <Button
                  size="sm"
                  variant="outline"
                  leftIcon={<FiChevronLeft aria-hidden="true" />}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  isDisabled={page <= 1 || isFetching}
                >
                  Prev
                </Button>
                <Text fontSize="sm" color="gray.500">
                  Page {page} of {totalPages}
                </Text>
                <Button
                  size="sm"
                  variant="outline"
                  rightIcon={<FiChevronRight aria-hidden="true" />}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  isDisabled={page >= totalPages || isFetching}
                >
                  Next
                </Button>
              </HStack>
            )}
          </>
        )}
      </VStack>

      <DeleteRoastDialog
        roast={pendingDelete}
        isDeleting={deleteRoast.isPending}
        onConfirm={confirmDelete}
        onClose={() => {
          if (!deleteRoast.isPending) setPendingDelete(null);
        }}
      />
    </PageWrapper>
  );
}

export default MyRoastsPage;
