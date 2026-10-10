import {
  Badge,
  Box,
  Button,
  Flex,
  FormControl,
  FormErrorMessage,
  FormLabel,
  HStack,
  Input,
  InputGroup,
  InputLeftElement,
  InputRightElement,
  List,
  ListItem,
  Spinner,
  Text,
  useColorModeValue,
} from '@chakra-ui/react';
import { useId, useState, type KeyboardEvent } from 'react';
import { FiSearch, FiX } from 'react-icons/fi';

import { MIN_SEARCH_LENGTH, useMovieSearch } from '../../hooks/useMovieSearch';
import type { MovieSearchResult } from '../../types/roast';
import { languageName, movieLabel } from './languages';
import { MoviePoster } from './MoviePoster';

export interface MovieSearchProps {
  value: MovieSearchResult | null;
  onChange: (movie: MovieSearchResult | null) => void;
  error?: string;
  isDisabled?: boolean;
}

/**
 * Search-as-you-type movie picker (ARIA combobox). Once a movie is picked it collapses to a
 * compact card with a "Change" button.
 */
export function MovieSearch({ value, onChange, error, isDisabled = false }: MovieSearchProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [active, setActive] = useState(0);
  const search = useMovieSearch(query);
  const inputId = useId();
  const listId = useId();

  const bg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.300');
  const activeBg = useColorModeValue('brand.50', 'whiteAlpha.200');
  const pickedBg = useColorModeValue('orange.50', 'whiteAlpha.100');

  const results = search.data ?? [];
  const trimmed = query.trim();
  const showList = isOpen && trimmed.length >= MIN_SEARCH_LENGTH;

  const pick = (movie: MovieSearchResult) => {
    onChange(movie);
    setQuery('');
    setIsOpen(false);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsOpen(false);
      return;
    }
    if (!showList || results.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((i) => (i - 1 + results.length) % results.length);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      pick(results[Math.min(active, results.length - 1)]);
    }
  };

  if (value) {
    return (
      <FormControl>
        <FormLabel fontSize="sm" fontWeight="medium" mb={1}>
          Movie
        </FormLabel>
        <Flex
          align="center"
          gap={3}
          p={3}
          borderRadius="xl"
          borderWidth="2px"
          borderColor="brand.400"
          bg={pickedBg}
          data-testid="picked-movie"
        >
          <MoviePoster url={value.poster_url} title={value.title} w="44px" />
          <Box flex="1" minW={0}>
            <Text fontWeight="semibold" noOfLines={1}>
              {movieLabel(value)}
            </Text>
            <Text fontSize="xs" color="gray.500">
              {languageName(value.original_language)}
            </Text>
          </Box>
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<FiX aria-hidden="true" />}
            onClick={() => onChange(null)}
            isDisabled={isDisabled}
          >
            Change
          </Button>
        </Flex>
      </FormControl>
    );
  }

  const activeId = showList && results.length > 0 ? `${listId}-${active}` : undefined;

  return (
    <FormControl isInvalid={Boolean(error)} position="relative">
      <FormLabel htmlFor={inputId} fontSize="sm" fontWeight="medium" mb={1}>
        Movie
      </FormLabel>
      <InputGroup size="lg">
        <InputLeftElement pointerEvents="none" color="gray.400">
          <FiSearch aria-hidden="true" />
        </InputLeftElement>
        <Input
          id={inputId}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={activeId}
          autoComplete="off"
          placeholder="Search a movie… Leo, Jailer, Vikram"
          value={query}
          isDisabled={isDisabled}
          borderRadius="xl"
          borderWidth="2px"
          borderColor={error ? 'chili.500' : borderColor}
          bg={bg}
          _focus={{ borderColor: error ? 'chili.500' : 'brand.500' }}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setIsOpen(false)}
          onKeyDown={onKeyDown}
        />
        {search.isFetching && (
          <InputRightElement>
            <Spinner size="sm" color="brand.500" label="Searching" />
          </InputRightElement>
        )}
      </InputGroup>
      {error && <FormErrorMessage>{error}</FormErrorMessage>}

      {showList && (
        <List
          id={listId}
          role="listbox"
          aria-label="Movie results"
          position="absolute"
          zIndex="dropdown"
          left={0}
          right={0}
          mt={1}
          maxH="320px"
          overflowY="auto"
          bg={bg}
          borderWidth="1px"
          borderColor={borderColor}
          borderRadius="xl"
          boxShadow="xl"
          py={1}
        >
          {results.map((movie, index) => (
            <ListItem
              key={movie.tmdb_id}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              px={3}
              py={2}
              cursor="pointer"
              bg={index === active ? activeBg : undefined}
              onMouseEnter={() => setActive(index)}
              // mousedown, not click: it fires before the input's blur closes the list.
              onMouseDown={(e) => {
                e.preventDefault();
                pick(movie);
              }}
            >
              <HStack spacing={3} align="center">
                <MoviePoster url={movie.poster_url} title={movie.title} w="36px" />
                <Box minW={0} flex="1">
                  <Text fontWeight="medium" noOfLines={1}>
                    {movieLabel(movie)}
                  </Text>
                  <Text fontSize="xs" color="gray.500" noOfLines={1}>
                    {movie.overview || 'No plot summary yet'}
                  </Text>
                </Box>
                <Badge
                  variant="subtle"
                  colorScheme={movie.original_language === 'ta' ? 'orange' : 'gray'}
                  borderRadius="full"
                  flexShrink={0}
                >
                  {languageName(movie.original_language)}
                </Badge>
              </HStack>
            </ListItem>
          ))}
          {!search.isFetching && search.isSuccess && results.length === 0 && (
            <ListItem px={3} py={3} color="gray.500" fontSize="sm">
              Indha padam kedaikala machan. Spelling check pannunga.
            </ListItem>
          )}
          {search.isError && (
            <ListItem px={3} py={3} color="chili.500" fontSize="sm">
              Search velai seiyala. Konjam neram kazhichu try pannunga.
            </ListItem>
          )}
        </List>
      )}
    </FormControl>
  );
}

export default MovieSearch;
