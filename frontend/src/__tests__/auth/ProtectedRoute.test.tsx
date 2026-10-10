import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { ProtectedRoute } from '../../components/auth/ProtectedRoute';
import { renderWithProviders } from '../test-utils';

describe('ProtectedRoute', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('shows a sign-in prompt instead of the content when logged out', () => {
    renderWithProviders(
      <ProtectedRoute>
        <p>Secret roasts</p>
      </ProtectedRoute>,
      ['/my-roasts'],
    );

    expect(screen.getByText(/My Roasts paakka login pannunga machan/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument();
    expect(screen.queryByText('Secret roasts')).not.toBeInTheDocument();
  });
});
