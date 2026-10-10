import { useToast } from '@chakra-ui/react';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../lib/tokenStorage';
import { AUTH_EXPIRED_EVENT, getErrorInfo } from '../services/api';
import * as authService from '../services/authService';
import type { TokenPair, User } from '../types';
import { AuthContext, type AuthContextValue } from './authContextValue';

function currentPath(): string {
  const { pathname, search, hash } = window.location;
  return `${pathname}${search}${hash}`;
}

export interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [user, setUser] = useState<User | null>(null);
  // Captured at first render (before child effects such as the OAuth callback
  // store fresh tokens), so the callback flow doesn't trigger a duplicate load.
  const hadTokenOnMount = useRef<boolean>(getAccessToken() !== null);
  const [isLoading, setIsLoading] = useState<boolean>(hadTokenOnMount.current);

  useEffect(() => {
    if (!hadTokenOnMount.current) return undefined;
    let cancelled = false;
    authService
      .getMe()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // Keep tokens on pure network errors (server down); drop them otherwise.
        if (getErrorInfo(err).status !== null) clearTokens();
        setUser(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onExpired = (): void => {
      setUser(null);
      setIsLoading(false);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  const signIn = useCallback((returnTo?: string): void => {
    authService.startGoogleSignIn(returnTo ?? currentPath());
  }, []);

  const signOut = useCallback(async (): Promise<void> => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await authService.logout(refreshToken);
      } catch {
        // Logging out locally is what matters; ignore server errors.
      }
    }
    clearTokens();
    setUser(null);
    queryClient.clear();
    toast({
      title: 'Signed out',
      description: 'Poitu varen machan! See you soon 👋',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  }, [queryClient, toast]);

  const completeSignIn = useCallback(async (tokens: TokenPair): Promise<User> => {
    setTokens(tokens.access_token, tokens.refresh_token);
    setIsLoading(true);
    try {
      const me = await authService.getMe();
      setUser(me);
      return me;
    } catch (err) {
      clearTokens();
      setUser(null);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshUser = useCallback(async (): Promise<void> => {
    if (!getAccessToken()) {
      setUser(null);
      return;
    }
    const me = await authService.getMe();
    setUser(me);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      signIn,
      signOut,
      completeSignIn,
      refreshUser,
    }),
    [user, isLoading, signIn, signOut, completeSignIn, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
