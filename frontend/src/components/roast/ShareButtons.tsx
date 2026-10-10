import { Button, Wrap, WrapItem, useToast } from '@chakra-ui/react';
import { FaWhatsapp, FaXTwitter } from 'react-icons/fa6';
import { FiCopy, FiShare2 } from 'react-icons/fi';

import { buildPermalink, buildShareText, buildWhatsAppUrl, buildXUrl } from '../../lib/share';

export interface ShareButtonsProps {
  roastId: string;
  roastText: string;
  movieTitle?: string;
}

function canNativeShare(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function';
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === 'AbortError';
}

export function ShareButtons({ roastId, roastText, movieTitle }: ShareButtonsProps) {
  const toast = useToast();
  const permalink = buildPermalink(roastId);
  const shareText = buildShareText(roastText, permalink);

  const handleCopy = async () => {
    try {
      if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
        throw new Error('Clipboard unavailable');
      }
      await navigator.clipboard.writeText(shareText);
      toast({ status: 'success', title: 'Copied! Group-la podu 😎', duration: 2500, isClosable: true });
    } catch {
      toast({
        status: 'error',
        title: 'Copy aagala machan',
        description: 'Your browser blocked the clipboard. Select the text and copy it manually.',
        duration: 4000,
        isClosable: true,
      });
    }
  };

  const handleNativeShare = async () => {
    try {
      await navigator.share({
        title: movieTitle ? `${movieTitle} roast 🎬` : 'Movie Roast 🎬',
        text: roastText,
        url: permalink,
      });
    } catch (err) {
      if (!isAbortError(err)) {
        toast({ status: 'error', title: 'Share aagala, try Copy instead', duration: 3000, isClosable: true });
      }
    }
  };

  return (
    <Wrap spacing={2} role="group" aria-label="Share this roast">
      <WrapItem>
        <Button
          size="sm"
          variant="outline"
          leftIcon={<FiCopy aria-hidden="true" />}
          onClick={() => void handleCopy()}
          aria-label="Copy roast and link"
        >
          Copy
        </Button>
      </WrapItem>
      <WrapItem>
        <Button
          as="a"
          href={buildWhatsAppUrl(roastText, permalink)}
          target="_blank"
          rel="noopener noreferrer"
          size="sm"
          colorScheme="green"
          leftIcon={<FaWhatsapp aria-hidden="true" />}
          aria-label="Share on WhatsApp"
        >
          WhatsApp
        </Button>
      </WrapItem>
      <WrapItem>
        <Button
          as="a"
          href={buildXUrl(roastText, permalink)}
          target="_blank"
          rel="noopener noreferrer"
          size="sm"
          colorScheme="gray"
          leftIcon={<FaXTwitter aria-hidden="true" />}
          aria-label="Share on X"
        >
          Post
        </Button>
      </WrapItem>
      {canNativeShare() && (
        <WrapItem>
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<FiShare2 aria-hidden="true" />}
            onClick={() => void handleNativeShare()}
            aria-label="Share via device"
          >
            Share
          </Button>
        </WrapItem>
      )}
    </Wrap>
  );
}

export default ShareButtons;
