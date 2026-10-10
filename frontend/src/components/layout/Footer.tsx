import { Box, Container, Link, Text, useColorModeValue } from '@chakra-ui/react';

export function Footer() {
  const color = useColorModeValue('gray.600', 'gray.400');

  return (
    <Box as="footer" py={6} mt="auto">
      <Container maxW="5xl">
        <Text textAlign="center" fontSize="sm" color={color}>
          Roast the movie, not the people 🙏
        </Text>
        <Text textAlign="center" fontSize="xs" color={color} mt={2}>
          Movie data from{' '}
          <Link href="https://www.themoviedb.org/" isExternal>
            TMDB
          </Link>
          . This product uses the TMDB API but is not endorsed or certified by TMDB. GIFs by{' '}
          <Link href="https://giphy.com/" isExternal>
            GIPHY
          </Link>
          .
        </Text>
      </Container>
    </Box>
  );
}

export default Footer;
