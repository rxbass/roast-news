import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { getErrorInfo } from '../services/api';
import {
  createRoast,
  deleteRoast,
  getMyRoasts,
  getRoast,
  MY_ROASTS_PAGE_SIZE,
} from '../services/roastService';
import type { Roast, RoastCreate, RoastList } from '../types/roast';

/** Centralised React Query keys for the roast module. */
export const roastKeys = {
  all: ['roasts'] as const,
  detail: (id: string) => ['roasts', 'detail', id] as const,
  mine: () => ['roasts', 'me'] as const,
  minePage: (page: number, size: number) => ['roasts', 'me', { page, size }] as const,
};

/** Never retry client errors (404, 401, ...); retry server/network errors once. */
function retryUnlessClientError(failureCount: number, error: unknown): boolean {
  const { status } = getErrorInfo(error);
  if (status !== null && status >= 400 && status < 500) return false;
  return failureCount < 1;
}

export function useCreateRoast(): UseMutationResult<Roast, unknown, RoastCreate> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createRoast,
    onSuccess: (roast) => {
      queryClient.setQueryData(roastKeys.detail(roast.id), roast);
      void queryClient.invalidateQueries({ queryKey: roastKeys.mine() });
    },
  });
}

export function useRoast(id: string | undefined): UseQueryResult<Roast, unknown> {
  return useQuery({
    queryKey: roastKeys.detail(id ?? ''),
    queryFn: () => getRoast(id ?? ''),
    enabled: Boolean(id),
    retry: retryUnlessClientError,
  });
}

export function useMyRoasts(
  page: number,
  size: number = MY_ROASTS_PAGE_SIZE,
): UseQueryResult<RoastList, unknown> {
  return useQuery({
    queryKey: roastKeys.minePage(page, size),
    queryFn: () => getMyRoasts(page, size),
    placeholderData: keepPreviousData,
    retry: retryUnlessClientError,
  });
}

export function useDeleteRoast(): UseMutationResult<void, unknown, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteRoast,
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: roastKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: roastKeys.mine() });
    },
  });
}
