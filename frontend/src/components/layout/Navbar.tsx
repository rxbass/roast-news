import { Box, Container, Flex, HStack, Heading, Link, useColorModeValue } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';

import { MotionBox } from '../../lib/motion';

export interface NavbarProps {
  /**
   * Right-side slot. AppLayout mounts <AuthControls /> (sign-in button / user menu) here.
   * Renders nothing by default.
   */
  rightSlot?: ReactNode;
}

export function Navbar({ rightSlot = null }: NavbarProps) {
  const bg = useColorModeValue('whiteAlpha.800', 'blackAlpha.500');
  const borderColor = useColorModeValue('orange.100', 'whiteAlpha.200');

  return (
    <Box
      as="header"
      position="sticky"
      top={0}
      zIndex="sticky"
      bg={bg}
      backdropFilter="blur(12px)"
      borderBottomWidth="1px"
      borderColor={borderColor}
    >
      <Container maxW="5xl" py={3}>
        <Flex align="center" justify="space-between" gap={4}>
          <MotionBox whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
            <Link as={RouterLink} to="/" _hover={{ textDecoration: 'none' }} aria-label="Roast News home">
              <Heading
                as="span"
                size="md"
                bgGradient="linear(to-r, brand.500, chili.500)"
                bgClip="text"
              >
                Roast News 🌶
              </Heading>
            </Link>
          </MotionBox>
          <HStack spacing={3} data-testid="navbar-right-slot">
            {rightSlot}
          </HStack>
        </Flex>
      </Container>
    </Box>
  );
}

export default Navbar;
