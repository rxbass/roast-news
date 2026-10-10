import type { StackProps } from '@chakra-ui/react';
import { Children, isValidElement, type ReactNode } from 'react';
import type { Variants } from 'framer-motion';

import { MotionBox } from '../../lib/motion';

const containerVariants: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export interface AnimatedListProps {
  children: ReactNode;
  /** Vertical gap between items (Chakra spacing token). */
  spacing?: StackProps['spacing'];
}

/**
 * Staggers its children in. Give each child a stable `key` so items keep
 * identity across re-renders (Children.toArray preserves those keys).
 */
export function AnimatedList({ children, spacing = 4 }: AnimatedListProps) {
  const items = Children.toArray(children);

  return (
    <MotionBox
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      display="flex"
      flexDirection="column"
      gap={spacing}
      role="list"
    >
      {items.map((child, index) => (
        <MotionBox
          key={isValidElement(child) && child.key !== null ? child.key : index}
          variants={itemVariants}
          role="listitem"
        >
          {child}
        </MotionBox>
      ))}
    </MotionBox>
  );
}

export default AnimatedList;
