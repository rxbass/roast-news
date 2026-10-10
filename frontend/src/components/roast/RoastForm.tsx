import { Box, chakra, VStack } from '@chakra-ui/react';
import { useState, type FormEvent } from 'react';

import type { MovieSearchResult, RoastCreate, SpiceLevel } from '../../types/roast';
import { MovieSearch } from '../movie';
import { GradientButton } from '../ui';
import { DEFAULT_SPICE } from './spice';
import { SpiceSelector } from './SpiceSelector';

export interface RoastFormProps {
  onSubmit: (payload: RoastCreate) => void;
  isSubmitting?: boolean;
  /** Seconds left before another roast is allowed (429 cooldown). */
  cooldownSeconds?: number;
}

export const PICK_A_MOVIE = 'Mudhalla oru padam select pannu machan 🎬';

export function RoastForm({ onSubmit, isSubmitting = false, cooldownSeconds = 0 }: RoastFormProps) {
  const [movie, setMovie] = useState<MovieSearchResult | null>(null);
  const [spice, setSpice] = useState<SpiceLevel>(DEFAULT_SPICE);
  const [error, setError] = useState<string | undefined>(undefined);

  const isCoolingDown = cooldownSeconds > 0;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting || isCoolingDown) return;
    if (!movie) {
      setError(PICK_A_MOVIE);
      return;
    }
    setError(undefined);
    onSubmit({ tmdb_id: movie.tmdb_id, spice_level: spice });
  };

  return (
    <Box as="form" onSubmit={handleSubmit} noValidate w="full" aria-label="Roast a movie">
      <chakra.fieldset disabled={isSubmitting} border="0" p={0} m={0} minW={0}>
        <VStack spacing={5} align="stretch">
          <MovieSearch
            value={movie}
            error={error}
            isDisabled={isSubmitting}
            onChange={(picked) => {
              setMovie(picked);
              if (picked) setError(undefined);
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
