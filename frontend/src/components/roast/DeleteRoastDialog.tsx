import {
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Button,
} from '@chakra-ui/react';
import { useRef } from 'react';

import type { Roast } from '../../types/roast';

export interface DeleteRoastDialogProps {
  roast: Roast | null;
  isDeleting: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function DeleteRoastDialog({ roast, isDeleting, onConfirm, onClose }: DeleteRoastDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  return (
    <AlertDialog
      isOpen={roast !== null}
      leastDestructiveRef={cancelRef}
      onClose={onClose}
      isCentered
      size={{ base: 'xs', sm: 'md' }}
    >
      <AlertDialogOverlay>
        <AlertDialogContent mx={4}>
          <AlertDialogHeader fontSize="lg" fontWeight="bold">
            Delete this roast?
          </AlertDialogHeader>
          <AlertDialogBody>
            &ldquo;{roast?.article_title || roast?.source_domain}&rdquo; will be gone for good. Sure-a machan?
          </AlertDialogBody>
          <AlertDialogFooter gap={3}>
            <Button ref={cancelRef} onClick={onClose} variant="ghost" isDisabled={isDeleting}>
              Cancel
            </Button>
            <Button colorScheme="red" onClick={onConfirm} isLoading={isDeleting}>
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialogOverlay>
    </AlertDialog>
  );
}

export default DeleteRoastDialog;
