import { createContext } from 'react';

import type { TokenPair, User } from '../types';

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  /** Full-page redirect to Google. Defaults to the current path. */
  signIn: (returnTo?: string) => void;
  signOut: () => Promise<void>;
  /** Store the token pair, load the user and return it. */
  completeSignIn: (tokens: TokenPair) => Promise<User>;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
