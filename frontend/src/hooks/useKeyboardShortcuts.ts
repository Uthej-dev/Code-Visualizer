import { useEffect } from 'react';

export interface ShortcutHandlers {
  prev: () => void;
  next: () => void;
  first: () => void;
  last: () => void;
  togglePlay: () => void;
  run: () => void;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.closest('.monaco-editor')) return true;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

/**
 * Global shortcuts: ←/→ step, Home/End first/last, Space play/pause,
 * Ctrl/Cmd+Enter run. Ignored while typing in the editor or a form field
 * (except Ctrl/Cmd+Enter, which always runs).
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers, enabled: boolean): void {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        handlers.run();
        return;
      }
      if (!enabled || event.altKey || event.ctrlKey || event.metaKey || isTypingTarget(event.target)) return;
      const action = {
        ArrowLeft: handlers.prev,
        ArrowRight: handlers.next,
        Home: handlers.first,
        End: handlers.last,
        ' ': handlers.togglePlay,
      }[event.key];
      if (!action) return;
      // Space on a focused button would also "click" it; handle it once here.
      event.preventDefault();
      action();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [handlers, enabled]);
}
