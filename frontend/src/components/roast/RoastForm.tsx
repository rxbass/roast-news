import { Box, chakra, VStack } from '@chakra-ui/react';
import { useState, type FormEvent } from 'react';

import type { RoastCreate, SpiceLevel } from '../../types/roast';
import { AnimatedInput, GradientButton } from '../ui';
import { DEFAULT_SPICE } from './spice';
import { SpiceSelector } from './SpiceSelector';
import { validateNewsUrl } from './validateUrl';

export interface RoastFormProps {
  onSubmit: (payload: RoastCreate) => void;
  isSubmitting?: boolean;
  /** Seconds left before another roast is allowed (429 cooldown). */
  cooldownSeconds?: number;
}

export function RoastForm({ onSubmit, isSubmitting = false, cooldownSeconds = 0 }: RoastFormProps) {
  const [url, setUrl] = useState('');
  const [spice, setSpice] = useState<SpiceLevel>(DEFAULT_SPICE);
  const [error, setError] = useState<string | undefined>(undefined);

  const isCoolingDown = cooldownSeconds > 0;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting || isCoolingDown) return;
    const message = validateNewsUrl(url);
    if (message) {
      setError(message);
      return;
    }
    setError(undefined);
    onSubmit({ url: url.trim(), spice_level: spice });
  };

  return (
    <Box as="form" onSubmit={handleSubmit} noValidate w="full" aria-label="Roast a news article">
      <chakra.fieldset disabled={isSubmitting} border="0" p={0} m={0} minW={0}>
        <VStack spacing={5} align="stretch">
          <AnimatedInput
            label="News link"
            name="url"
            type="url"
            inputMode="url"
            autoComplete="off"
            placeholder="https://example.com/news/some-story"
            value={url}
            error={error}
            onChange={(e) => {
              setUrl(e.target.value);
              if (error) setError(undefined);
            }}
          />
          <SpiceSelector value={spice} onChange={setSpice} isDisabled={isSubmitting} />
          <GradientButton
            type="submit"
            size="lg"
            w="full"
            isLoading={isSubmitting}
            isDisabled={isCoolingDown}
          >
            {isCoolingDown ? `Wait ${cooldownSeconds}s ⏳` : 'Roast Pannu! 🔥'}
          </GradientButton>
        </VStack>
      </chakra.fieldset>
    </Box>
  );
}

export default RoastForm;
