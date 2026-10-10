import { useCallback, useEffect, useState } from 'react';

export interface RoastCooldown {
  secondsLeft: number;
  isCoolingDown: boolean;
  start: (seconds: number) => void;
  reset: () => void;
}

/** Simple 1-second countdown used for 429 Retry-After handling. */
export function useRoastCooldown(): RoastCooldown {
  const [secondsLeft, setSecondsLeft] = useState(0);

  useEffect(() => {
    if (secondsLeft <= 0) return undefined;
    const timer = window.setTimeout(() => {
      setSecondsLeft((s) => Math.max(0, s - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [secondsLeft]);

  const start = useCallback((seconds: number) => {
    setSecondsLeft(Math.max(0, Math.ceil(seconds)));
  }, []);

  const reset = useCallback(() => setSecondsLeft(0), []);

  return { secondsLeft, isCoolingDown: secondsLeft > 0, start, reset };
}
