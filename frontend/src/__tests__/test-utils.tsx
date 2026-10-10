import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';

import { AuthProvider } from '../context/AuthContext';
import theme from '../theme';

export interface RenderOptions {
  /** Wrap the tree in <AuthProvider> (needed by anything that calls useAuth). Default true. */
  withAuth?: boolean;
}

/** Render a component inside the same providers as the real app. */
export function renderWithProviders(
  ui: ReactElement,
  initialEntries: string[] = ['/'],
  { withAuth = true }: RenderOptions = {},
): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const routed = <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>;

  return render(
    <ChakraProvider theme={theme}>
      <QueryClientProvider client={queryClient}>
        {withAuth ? <AuthProvider>{routed}</AuthProvider> : routed}
      </QueryClientProvider>
    </ChakraProvider>,
  );
}
