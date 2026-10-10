import { SkeletonCircle } from '@chakra-ui/react';

import { useAuth } from '../../hooks/useAuth';
import { GoogleSignInButton } from './GoogleSignInButton';
import { UserMenu } from './UserMenu';

/** Navbar right slot: loading placeholder, user menu, or sign-in button. */
export function AuthControls() {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) return <SkeletonCircle size="8" aria-label="Loading account" />;
  if (isAuthenticated) return <UserMenu />;
  return <GoogleSignInButton compact />;
}

export default AuthControls;
