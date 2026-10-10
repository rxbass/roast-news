import { Spinner, type ButtonProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';

import { MotionButton } from '../../lib/motion';

export interface GradientButtonProps
  extends Omit<ButtonProps, 'transition' | 'children' | 'isLoading' | 'isDisabled'> {
  children: ReactNode;
  isLoading?: boolean;
  isDisabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

export function GradientButton({
  children,
  isLoading = false,
  isDisabled = false,
  type = 'button',
  ...rest
}: GradientButtonProps) {
  const disabled = isDisabled || isLoading;

  return (
    <MotionButton
      type={type}
      disabled={disabled}
      aria-busy={isLoading}
      whileHover={disabled ? undefined : { scale: 1.02, y: -2 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      display="inline-flex"
      alignItems="center"
      justifyContent="center"
      gap={2}
      px={6}
      py={3}
      borderRadius="full"
      fontWeight="semibold"
      color="white"
      bgGradient="linear(to-r, brand.500, chili.500)"
      boxShadow="md"
      cursor={disabled ? 'not-allowed' : 'pointer'}
      opacity={disabled ? 0.7 : 1}
      _hover={disabled ? undefined : { boxShadow: 'lg', bgGradient: 'linear(to-r, brand.600, chili.600)' }}
      _focusVisible={{ outline: '2px solid', outlineColor: 'brand.300', outlineOffset: '2px' }}
      {...rest}
    >
      {isLoading && <Spinner size="sm" />}
      {children}
    </MotionButton>
  );
}

export default GradientButton;
