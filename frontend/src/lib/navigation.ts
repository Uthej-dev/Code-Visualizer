/**
 * Step navigation state. Every step in a trace is a complete snapshot, so
 * moving to any index (forwards, backwards or via the timeline) restores the
 * exact program state — nothing is replayed or reversed.
 */

export interface NavState {
  index: number;
  total: number;
  playing: boolean;
}

export type NavAction =
  | { type: 'load'; total: number }
  | { type: 'first' }
  | { type: 'prev' }
  | { type: 'next' }
  | { type: 'last' }
  | { type: 'jump'; index: number }
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'toggle' }
  | { type: 'tick' }
  | { type: 'clear' };

export const initialNav: NavState = { index: 0, total: 0, playing: false };

const clamp = (i: number, total: number) => (total === 0 ? 0 : Math.min(Math.max(0, Math.round(i)), total - 1));

export function navReducer(state: NavState, action: NavAction): NavState {
  const last = Math.max(0, state.total - 1);
  switch (action.type) {
    case 'load':
      return { index: 0, total: Math.max(0, action.total), playing: false };
    case 'clear':
      return initialNav;
    case 'first':
      return { ...state, index: 0, playing: false };
    case 'prev':
      return { ...state, index: clamp(state.index - 1, state.total), playing: false };
    case 'next':
      return { ...state, index: clamp(state.index + 1, state.total), playing: false };
    case 'last':
      return { ...state, index: last, playing: false };
    case 'jump':
      return { ...state, index: clamp(action.index, state.total), playing: false };
    case 'play':
      if (state.total <= 1) return state;
      // Pressing play at the end restarts from the beginning.
      return { ...state, playing: true, index: state.index >= last ? 0 : state.index };
    case 'pause':
      return { ...state, playing: false };
    case 'toggle':
      return navReducer(state, { type: state.playing ? 'pause' : 'play' });
    case 'tick': {
      if (!state.playing) return state;
      const index = clamp(state.index + 1, state.total);
      return { ...state, index, playing: index < last };
    }
    default:
      return state;
  }
}

export function canGoBack(state: NavState): boolean {
  return state.total > 0 && state.index > 0;
}

export function canGoForward(state: NavState): boolean {
  return state.total > 0 && state.index < state.total - 1;
}
