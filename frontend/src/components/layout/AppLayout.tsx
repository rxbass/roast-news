import { Box, Container, Flex } from '@chakra-ui/react';
import { Outlet } from 'react-router-dom';

import { AuthControls } from '../auth/AuthControls';
import { Footer } from './Footer';
import { Navbar } from './Navbar';

export function AppLayout() {
  return (
    <Flex direction="column" minH="100vh">
      <Navbar rightSlot={<AuthControls />} />
      <Box as="main" flex="1" py={{ base: 6, md: 10 }}>
        <Container maxW="5xl">
          <Outlet />
        </Container>
      </Box>
      <Footer />
    </Flex>
  );
}

export default AppLayout;
