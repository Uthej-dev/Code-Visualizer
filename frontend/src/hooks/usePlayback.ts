import { useEffect } from 'react';

/** Advances one step every `intervalMs` while `playing` is true. */
export function usePlayback(playing: boolean, intervalMs: number, tick: () => void): void {
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [playing, intervalMs, tick]);
}
