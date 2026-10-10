import { chakra, shouldForwardProp } from '@chakra-ui/react';
import { isValidMotionProp, motion } from 'framer-motion';

/**
 * Chakra + Framer Motion bridge: components that accept both Chakra style
 * props and Framer Motion animation props.
 *
 * Note: Chakra's `transition` style prop shadows Framer's `transition`, so pass
 * motion transitions inside `animate`/`whileHover` targets or `variants`.
 */
const forwardMotionProps = (prop: string): boolean =>
  isValidMotionProp(prop) || shouldForwardProp(prop);

export const MotionBox = chakra(motion.div, { shouldForwardProp: forwardMotionProps });

export const MotionButton = chakra(motion.button, { shouldForwardProp: forwardMotionProps });

export const MotionInput = chakra(motion.input, { shouldForwardProp: forwardMotionProps });
