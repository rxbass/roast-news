import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { NotFoundPage } from '../pages/NotFoundPage';
import { renderWithProviders } from './test-utils';

describe('NotFoundPage', () => {
  it('renders the 404 message and a way home', () => {
    renderWithProviders(<NotFoundPage />, ['/does-not-exist']);

    expect(screen.getByRole('heading', { name: '404' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /back to home/i })).toBeInTheDocument();
  });
});
