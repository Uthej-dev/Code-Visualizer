import { memo, type ReactNode } from 'react';
import type { Step } from '../types/trace';
import { canGoBack, canGoForward, type NavState } from '../lib/navigation';
import { IconFirst, IconLast, IconNext, IconPause, IconPlay, IconPrev, IconReset } from './Icons';

export const SPEEDS = [
  { label: '0.5×', ms: 1600 },
  { label: '1×', ms: 800 },
  { label: '2×', ms: 400 },
  { label: '4×', ms: 200 },
];

interface Props {
  nav: NavState;
  steps: Step[];
  speedMs: number;
  onSpeed: (ms: number) => void;
  onFirst: () => void;
  onPrev: () => void;
  onNext: () => void;
  onLast: () => void;
  onToggle: () => void;
  onReset: () => void;
  onJump: (index: number) => void;
  disabled: boolean;
}

function NavButton({ label, shortcut, onClick, disabled, children, primary = false }: { label: string; shortcut?: string; onClick: () => void; disabled: boolean; children: ReactNode; primary?: boolean }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={shortcut ? `${label} (${shortcut})` : label}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex h-8 items-center justify-center rounded-md px-2.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 disabled:cursor-not-allowed disabled:opacity-35 ${
        primary
          ? 'min-w-[2.75rem] bg-sky-500 text-ink-950 hover:bg-sky-400 disabled:hover:bg-sky-500'
          : 'border border-ink-600 bg-ink-800 text-slate-200 hover:border-ink-500 hover:bg-ink-700 disabled:hover:bg-ink-800'
      }`}
    >
      {children}
    </button>
  );
}

const TICK_COLORS: Partial<Record<Step['event'], string>> = {
  call: 'bg-emerald-400',
  return: 'bg-violet-400',
  exception: 'bg-rose-400',
};

/** Coloured markers on the timeline for calls, returns and exceptions. */
const TimelineTicks = memo(function TimelineTicks({ steps }: { steps: Step[] }) {
  if (steps.length < 2) return null;
  return (
    <div className="pointer-events-none absolute inset-x-[7px] top-0 h-1.5" aria-hidden="true">
      {steps.map((s) =>
        TICK_COLORS[s.event] ? (
          <span
            key={s.index}
            className={`absolute top-0 h-1.5 w-[2px] rounded-full ${TICK_COLORS[s.event]}`}
            style={{ left: `${(s.index / (steps.length - 1)) * 100}%` }}
          />
        ) : null,
      )}
    </div>
  );
});

export function Controls({ nav, steps, speedMs, onSpeed, onFirst, onPrev, onNext, onLast, onToggle, onReset, onJump, disabled }: Props) {
  const back = !disabled && canGoBack(nav);
  const forward = !disabled && canGoForward(nav);
  const total = nav.total;
  const step = steps[nav.index];
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2">
      <div className="flex items-center gap-1" role="group" aria-label="Step navigation">
        <NavButton label="First step" shortcut="Home" onClick={onFirst} disabled={!back}><IconFirst /></NavButton>
        <NavButton label="Previous step" shortcut="←" onClick={onPrev} disabled={!back}><IconPrev /></NavButton>
        <NavButton
          label={nav.playing ? 'Pause' : 'Play'}
          shortcut="Space"
          onClick={onToggle}
          disabled={disabled || total < 2}
          primary
        >
          {nav.playing ? <IconPause /> : <IconPlay />}
        </NavButton>
        <NavButton label="Next step" shortcut="→" onClick={onNext} disabled={!forward}><IconNext /></NavButton>
        <NavButton label="Last step" shortcut="End" onClick={onLast} disabled={!forward}><IconLast /></NavButton>
        <NavButton label="Reset: clear the visualization and edit the code" onClick={onReset} disabled={disabled}><IconReset /></NavButton>
      </div>

      <div className="flex min-w-[12rem] flex-1 items-center gap-3">
        <div className="relative flex-1 pt-2">
          <TimelineTicks steps={steps} />
          <input
            type="range"
            aria-label="Timeline: jump to a step"
            min={0}
            max={Math.max(0, total - 1)}
            value={nav.index}
            disabled={disabled || total < 2}
            onChange={(e) => onJump(Number(e.target.value))}
            className="cv-range w-full"
            aria-valuetext={total ? `Step ${nav.index + 1} of ${total}` : 'No steps'}
          />
        </div>
        <span className="shrink-0 font-mono text-xs tabular-nums text-slate-400" data-testid="step-indicator" aria-live="polite">
          Step <span className="text-slate-100">{total ? nav.index + 1 : 0}</span> / {total}
          {step?.line != null && <span className="ml-2 text-slate-500">line {step.line}</span>}
        </span>
      </div>

      <label className="flex items-center gap-2 text-xs text-slate-400">
        Speed
        <select
          value={speedMs}
          onChange={(e) => onSpeed(Number(e.target.value))}
          className="h-8 rounded-md border border-ink-600 bg-ink-800 px-2 text-xs text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
          aria-label="Playback speed"
        >
          {SPEEDS.map((s) => (
            <option key={s.ms} value={s.ms}>{s.label}</option>
          ))}
        </select>
      </label>
    </div>
  );
}
