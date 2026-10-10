import {
  Box,
  FormControl,
  FormLabel,
  SimpleGrid,
  Text,
  useColorModeValue,
  useRadio,
  useRadioGroup,
  type UseRadioProps,
} from '@chakra-ui/react';

import type { SpiceLevel } from '../../types/roast';
import { isSpiceLevel, SPICE_OPTIONS, type SpiceOption } from './spice';

interface SpiceCardProps extends UseRadioProps {
  option: SpiceOption;
}

function SpiceCard({ option, ...radioProps }: SpiceCardProps) {
  const { getInputProps, getRadioProps, getRootProps, state } = useRadio(radioProps);
  const bg = useColorModeValue('white', 'whiteAlpha.100');
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.300');
  const checkedBg = useColorModeValue(`${option.colorScheme}.50`, 'whiteAlpha.200');

  return (
    <Box as="label" {...getRootProps()} cursor={state.isDisabled ? 'not-allowed' : 'pointer'}>
      {/* The visual card is aria-hidden by useRadio, so label the input itself. */}
      <input {...getInputProps({ 'aria-label': `${option.label}: ${option.tagline}` })} />
      <Box
        {...getRadioProps()}
        h="full"
        px={3}
        py={{ base: 3, md: 4 }}
        borderWidth="2px"
        borderRadius="xl"
        borderColor={state.isChecked ? `${option.colorScheme}.500` : borderColor}
        bg={state.isChecked ? checkedBg : bg}
        boxShadow={state.isChecked ? 'md' : 'none'}
        textAlign="center"
        transitionProperty="common"
        transitionDuration="normal"
        _hover={{ borderColor: `${option.colorScheme}.400` }}
        _focusVisible={{ outline: '2px solid', outlineColor: 'brand.300', outlineOffset: '2px' }}
        data-testid={`spice-${option.value}`}
      >
        <Text fontSize={{ base: 'xl', md: '2xl' }} aria-hidden="true">
          {option.emoji}
        </Text>
        <Text fontWeight="bold" fontSize={{ base: 'sm', md: 'md' }}>
          {option.label}
        </Text>
        <Text fontSize="xs" color="gray.500">
          {option.tagline}
        </Text>
      </Box>
    </Box>
  );
}

export interface SpiceSelectorProps {
  value: SpiceLevel;
  onChange: (value: SpiceLevel) => void;
  isDisabled?: boolean;
  name?: string;
}

/** Accessible radio group of three spice cards (arrow keys move the selection). */
export function SpiceSelector({
  value,
  onChange,
  isDisabled = false,
  name = 'spice_level',
}: SpiceSelectorProps) {
  const { getRootProps, getRadioProps } = useRadioGroup({
    name,
    value,
    isDisabled,
    onChange: (next: string) => {
      if (isSpiceLevel(next)) onChange(next);
    },
  });

  return (
    <FormControl as="fieldset" isDisabled={isDisabled}>
      <FormLabel as="legend" fontSize="sm" fontWeight="medium" mb={2}>
        Spice level
      </FormLabel>
      <SimpleGrid
        {...getRootProps()}
        columns={3}
        spacing={{ base: 2, md: 3 }}
        role="radiogroup"
        aria-label="Spice level"
      >
        {SPICE_OPTIONS.map((option) => (
          <SpiceCard key={option.value} option={option} {...getRadioProps({ value: option.value })} />
        ))}
      </SimpleGrid>
    </FormControl>
  );
}

export default SpiceSelector;
