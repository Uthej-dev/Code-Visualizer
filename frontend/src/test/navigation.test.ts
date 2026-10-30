import { describe, expect, it } from 'vitest';
import { canGoBack, canGoForward, initialNav, navReducer, type NavAction, type NavState } from '../lib/navigation';

const run = (actions: NavAction[], start: NavState = initialNav) => actions.reduce(navReducer, start);

describe('navReducer', () => {
  it('loads a trace at the first step, paused', () => {
    expect(run([{ type: 'load', total: 5 }])).toEqual({ index: 0, total: 5, playing: false });
  });

  it('moves forwards and backwards and clamps at both ends', () => {
    const loaded = run([{ type: 'load', total: 3 }]);
    expect(run([{ type: 'prev' }], loaded).index).toBe(0);
    expect(run([{ type: 'next' }, { type: 'next' }, { type: 'next' }, { type: 'next' }], loaded).index).toBe(2);
    expect(run([{ type: 'next' }, { type: 'next' }, { type: 'prev' }], loaded).index).toBe(1);
  });

  it('jumps to first, last and arbitrary steps (timeline)', () => {
    const loaded = run([{ type: 'load', total: 10 }]);
    expect(run([{ type: 'last' }], loaded).index).toBe(9);
    expect(run([{ type: 'last' }, { type: 'first' }], loaded).index).toBe(0);
    expect(run([{ type: 'jump', index: 6 }], loaded).index).toBe(6);
    expect(run([{ type: 'jump', index: 99 }], loaded).index).toBe(9);
    expect(run([{ type: 'jump', index: -4 }], loaded).index).toBe(0);
  });

  it('plays until the last step, then stops', () => {
    let s = run([{ type: 'load', total: 3 }, { type: 'play' }]);
    expect(s.playing).toBe(true);
    s = run([{ type: 'tick' }], s);
    expect(s).toMatchObject({ index: 1, playing: true });
    s = run([{ type: 'tick' }], s);
    expect(s).toMatchObject({ index: 2, playing: false });
    expect(run([{ type: 'tick' }], s).index).toBe(2);
  });

  it('restarts from the beginning when play is pressed on the last step', () => {
    const s = run([{ type: 'load', total: 4 }, { type: 'last' }, { type: 'play' }]);
    expect(s).toMatchObject({ index: 0, playing: true });
  });

  it('manual navigation pauses playback', () => {
    const playing = run([{ type: 'load', total: 4 }, { type: 'play' }]);
    for (const type of ['next', 'prev', 'first', 'last'] as const) {
      expect(navReducer(playing, { type }).playing).toBe(false);
    }
    expect(navReducer(playing, { type: 'toggle' }).playing).toBe(false);
  });

  it('does nothing useful without steps', () => {
    expect(run([{ type: 'play' }])).toEqual(initialNav);
    expect(run([{ type: 'next' }]).index).toBe(0);
    expect(canGoBack(initialNav)).toBe(false);
    expect(canGoForward(initialNav)).toBe(false);
  });

  it('reports when Previous/Next are possible', () => {
    const loaded = run([{ type: 'load', total: 2 }]);
    expect([canGoBack(loaded), canGoForward(loaded)]).toEqual([false, true]);
    const end = run([{ type: 'next' }], loaded);
    expect([canGoBack(end), canGoForward(end)]).toEqual([true, false]);
  });
});
