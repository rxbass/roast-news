import { Box, Container, Text, useColorModeValue } from '@chakra-ui/react';

export function Footer() {
  const color = useColorModeValue('gray.600', 'gray.400');

  return (
    <Box as="footer" py={6} mt="auto">
      <Container maxW="5xl">
        <Text textAlign="center" fontSize="sm" color={color}>
          Roast the news, not the people 🙏
        </Text>
      </Container>
    </Box>
  );
}

export default Footer;
