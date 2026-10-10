import { Button, Text } from '@chakra-ui/react';
import { useContext } from 'react';

import { AuthContext } from '../../context/authContextValue';

/**
 * "Sign in to save your roasts" nudge for anonymous visitors. Reads the auth
 * context null-safely so it renders nothing outside an AuthProvider.
 */
export function SignInHint() {
  const auth = useContext(AuthContext);
  if (!auth || auth.isLoading || auth.isAuthenticated) return null;

  return (
    <Text fontSize="sm" color="gray.600" _dark={{ color: 'gray.300' }} textAlign="center">
      <Button variant="link" size="sm" colorScheme="brand" onClick={() => auth.signIn('/')}>
        Sign in
      </Button>{' '}
      to save your roasts and find them later in My Roasts.
    </Text>
  );
}

export default SignInHint;
