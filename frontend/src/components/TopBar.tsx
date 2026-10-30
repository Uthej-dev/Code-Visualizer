import type { Sample } from '../types/trace';
import { IconRun, Spinner } from './Icons';

interface Props {
  samples: Sample[];
  sampleId: string;
  onSample: (id: string) => void;
  onRun: () => void;
  running: boolean;
  status: 'editing' | 'running' | 'visualizing';
}

export function TopBar({ samples, sampleId, onSample, onRun, running, status }: Props) {
  return (
    <header className="flex shrink-0 flex-wrap items-center gap-3 border-b border-ink-700 bg-ink-900 px-4 py-2.5">
      <div className="flex items-center gap-2.5">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="7" fill="#151c2b" />
          <path d="M9 10l7 6-7 6" stroke="#38bdf8" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M18 22h6" stroke="#a78bfa" strokeWidth="3" strokeLinecap="round" />
        </svg>
        <div className="leading-tight">
          <h1 className="text-[15px] font-semibold text-slate-100">PyStep</h1>
          <p className="hidden text-[11px] text-slate-500 sm:block">Python code visualizer &amp; step-by-step debugger</p>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <label className="sr-only" htmlFor="sample-select">Load a sample program</label>
        <select
          id="sample-select"
          value={sampleId}
          onChange={(e) => onSample(e.target.value)}
          className="h-9 max-w-[14rem] rounded-md border border-ink-600 bg-ink-800 px-2 text-[13px] text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
        >
          <option value="" disabled>
            Load a sample…
          </option>
          {samples.map((s, i) => (
            <option key={s.id} value={s.id}>
              {i + 1}. {s.title}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={onRun}
          disabled={running}
          title="Run and visualize (Ctrl/⌘ + Enter)"
          className="inline-flex h-9 items-center gap-2 rounded-md bg-emerald-500 px-4 text-[13px] font-semibold text-ink-950 transition-colors hover:bg-emerald-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300 disabled:cursor-wait disabled:opacity-70"
        >
          {running ? <Spinner /> : <IconRun />}
          {running ? 'Running…' : status === 'visualizing' ? 'Run again' : 'Run & visualize'}
        </button>
      </div>
    </header>
  );
}
