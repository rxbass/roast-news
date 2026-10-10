import {
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  useColorModeValue,
  type InputProps,
} from '@chakra-ui/react';
import { forwardRef, useId } from 'react';

import { MotionInput } from '../../lib/motion';

export interface AnimatedInputProps extends Omit<InputProps, 'transition'> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const AnimatedInput = forwardRef<HTMLInputElement, AnimatedInputProps>(
  ({ label, error, helperText, id, isRequired, ...rest }, ref) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    const bg = useColorModeValue('white', 'whiteAlpha.100');
    const borderColor = useColorModeValue('gray.200', 'whiteAlpha.300');

    return (
      <FormControl isInvalid={Boolean(error)} isRequired={isRequired}>
        {label && (
          <FormLabel htmlFor={inputId} fontSize="sm" fontWeight="medium" mb={1}>
            {label}
          </FormLabel>
        )}
        <MotionInput
          ref={ref}
          id={inputId}
          whileFocus={{ scale: 1.01 }}
          w="full"
          px={4}
          py={3}
          borderRadius="xl"
          borderWidth="2px"
          borderColor={error ? 'chili.500' : borderColor}
          bg={bg}
          outline="none"
          _focus={{ borderColor: error ? 'chili.500' : 'brand.500' }}
          _placeholder={{ color: 'gray.400' }}
          aria-invalid={Boolean(error)}
          {...rest}
        />
        {error ? (
          <FormErrorMessage>{error}</FormErrorMessage>
        ) : (
          helperText && <FormHelperText>{helperText}</FormHelperText>
        )}
      </FormControl>
    );
  },
);

AnimatedInput.displayName = 'AnimatedInput';

export default AnimatedInput;
