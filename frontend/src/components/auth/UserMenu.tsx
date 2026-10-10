import {
  Avatar,
  Button,
  Menu,
  MenuButton,
  MenuDivider,
  MenuItem,
  MenuList,
  Text,
} from '@chakra-ui/react';
import { FiChevronDown, FiList, FiLogOut } from 'react-icons/fi';
import { Link as RouterLink } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';

export function UserMenu() {
  const { user, signOut } = useAuth();
  if (!user) return null;

  const displayName = user.full_name?.trim() || user.email;

  return (
    <Menu placement="bottom-end">
      <MenuButton
        as={Button}
        variant="ghost"
        borderRadius="full"
        size="sm"
        px={{ base: 1, md: 2 }}
        rightIcon={<FiChevronDown aria-hidden />}
        aria-label={`Account menu for ${displayName}`}
      >
        <Avatar size="xs" name={displayName} src={user.avatar_url ?? undefined} mr={{ base: 0, md: 2 }} />
        <Text as="span" display={{ base: 'none', md: 'inline' }} maxW="40" noOfLines={1}>
          {displayName}
        </Text>
      </MenuButton>
      <MenuList>
        <Text px={3} py={1} fontSize="xs" color="gray.500" noOfLines={1}>
          {user.email}
        </Text>
        <MenuDivider />
        <MenuItem as={RouterLink} to="/my-roasts" icon={<FiList aria-hidden />}>
          My Roasts
        </MenuItem>
        <MenuItem icon={<FiLogOut aria-hidden />} onClick={() => void signOut()}>
          Sign out
        </MenuItem>
      </MenuList>
    </Menu>
  );
}

export default UserMenu;
