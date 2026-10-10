import { screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getAccessToken, getRefreshToken } from '../../lib/tokenStorage';
import { AuthCallbackPage } from '../../pages/AuthCallbackPage';
import * as authService from '../../services/authService';
import type { User } from '../../types';
import { renderWithProviders } from '../test-utils';

vi.mock('../../services/authService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/authService')>();
  return { ...actual, getMe: vi.fn() };
});

const user: User = {
  id: 1,
  email: 'kumar@example.com',
  full_name: 'Kumar Swamy',
  avatar_url: null,
  created_at: '2026-01-01T00:00:00Z',
};

function renderCallback() {
  return renderWithProviders(
    <Routes>
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="/my-roasts" element={<p>My roasts landing</p>} />
      <Route path="/" element={<p>Home landing</p>} />
    </Routes>,
    ['/auth/callback'],
  );
}

const NONCE = '6f1c2a5e-0d4b-4a7e-9c3f-2b8d7e6a1f00';

describe('AuthCallbackPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.mocked(authService.getMe).mockReset();
  });

  afterEach(() => {
    window.history.replaceState(null, '', '/');
  });

  it('stores tokens, clears the hash and navigates to the saved returnTo', async () => {
    vi.mocked(authService.getMe).mockResolvedValue(user);
    window.sessionStorage.setItem(authService.RETURN_TO_KEY, '/my-roasts');
    window.sessionStorage.setItem(authService.OAUTH_NONCE_KEY, NONCE);
    window.history.replaceState(
      null,
      '',
      `/auth/callback#access_token=acc-1&refresh_token=ref-1&token_type=bearer&nonce=${NONCE}`,
    );

    renderCallback();

    expect(await screen.findByText('My roasts landing')).toBeInTheDocument();
    expect(getAccessToken()).toBe('acc-1');
    expect(getRefreshToken()).toBe('ref-1');
    expect(window.location.hash).toBe('');
    expect(window.sessionStorage.getItem(authService.RETURN_TO_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(authService.OAUTH_NONCE_KEY)).toBeNull();
    expect(await screen.findByText(/Vanakkam, Kumar!/)).toBeInTheDocument();
  });

  it('ignores an unsafe returnTo and lands on home', async () => {
    vi.mocked(authService.getMe).mockResolvedValue(user);
    window.sessionStorage.setItem(authService.RETURN_TO_KEY, '//evil.example.com');
    window.sessionStorage.setItem(authService.OAUTH_NONCE_KEY, NONCE);
    window.history.replaceState(null, '', `/auth/callback#access_token=a&refresh_token=r&nonce=${NONCE}`);

    renderCallback();

    expect(await screen.findByText('Home landing')).toBeInTheDocument();
  });

  it.each([
    ['no sign-in was started in this tab', null, NONCE],
    ['the nonce does not match', NONCE, 'attacker-nonce-0000000000'],
    ['the link carries no nonce', NONCE, null],
  ])('rejects tokens when %s (login CSRF)', async (_label, stored, inLink) => {
    if (stored) window.sessionStorage.setItem(authService.OAUTH_NONCE_KEY, stored);
    const nonceParam = inLink ? `&nonce=${inLink}` : '';
    window.history.replaceState(null, '', `/auth/callback#access_token=evil&refresh_token=evil${nonceParam}`);

    renderCallback();

    expect(await screen.findByRole('button', { name: /back to home/i })).toBeInTheDocument();
    expect(authService.getMe).not.toHaveBeenCalled();
    expect(getAccessToken()).toBeNull();
  });

  it('shows a friendly message for an error hash', async () => {
    window.history.replaceState(null, '', '/auth/callback#error=access_denied');

    renderCallback();

    expect(await screen.findByText(/Login cancel pannitinga, paravala!/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /back to home/i })).toBeInTheDocument();
    expect(authService.getMe).not.toHaveBeenCalled();
    expect(getAccessToken()).toBeNull();
    await waitFor(() => expect(window.location.hash).toBe(''));
  });
});
