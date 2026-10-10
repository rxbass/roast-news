import type { BoxProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';

import { MotionBox } from '../../lib/motion';

export interface PageWrapperProps extends Omit<BoxProps, 'transition'> {
  children: ReactNode;
}

export function PageWrapper({ children, ...rest }: PageWrapperProps) {
  return (
    <MotionBox
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0, transition: { duration: 0.3 } }}
      exit={{ opacity: 0, x: 20, transition: { duration: 0.3 } }}
      w="full"
      minH="full"
      {...rest}
    >
      {children}
    </MotionBox>
  );
}

export default PageWrapper;
