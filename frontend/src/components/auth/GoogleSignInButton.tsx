import { Box, Button, type ButtonProps } from '@chakra-ui/react';
import { FcGoogle } from 'react-icons/fc';

import { useAuth } from '../../hooks/useAuth';

export interface GoogleSignInButtonProps extends Omit<ButtonProps, 'onClick' | 'children'> {
  /** Where to land after sign-in. Defaults to the current path. */
  returnTo?: string;
  /** Shorter label on small screens (navbar). */
  compact?: boolean;
}

export function GoogleSignInButton({ returnTo, compact = false, ...rest }: GoogleSignInButtonProps) {
  const { signIn } = useAuth();

  return (
    <Button
      leftIcon={<FcGoogle aria-hidden />}
      variant="outline"
      colorScheme="gray"
      borderRadius="full"
      size={compact ? 'sm' : 'md'}
      onClick={() => signIn(returnTo)}
      aria-label="Sign in with Google"
      {...rest}
    >
      {compact ? (
        <>
          <Box as="span" display={{ base: 'inline', md: 'none' }}>
            Sign in
          </Box>
          <Box as="span" display={{ base: 'none', md: 'inline' }}>
            Sign in with Google
          </Box>
        </>
      ) : (
        'Sign in with Google'
      )}
    </Button>
  );
}

export default GoogleSignInButton;
