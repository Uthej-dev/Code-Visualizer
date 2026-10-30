import { Spinner } from './Icons';

export function MemoryEmptyState() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-sm text-center">
        <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-ink-600 bg-ink-850">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="1.7" aria-hidden="true">
            <rect x="3" y="4" width="7" height="6" rx="1.5" />
            <rect x="14" y="13" width="7" height="7" rx="1.5" />
            <path d="M10 7h3a2 2 0 0 1 2 2v4" strokeLinecap="round" />
          </svg>
        </div>
        <h2 className="text-[15px] font-semibold text-slate-100">See your program's memory</h2>
        <p className="mt-1.5 text-[13px] leading-relaxed text-slate-400">
          Variables, lists, dictionaries and function calls will appear here, step by step.
        </p>
        <ol className="mx-auto mt-4 flex max-w-xs flex-col gap-2 text-left text-[13px] text-slate-300">
          <li className="flex gap-2"><Num n={1} /> Write Python code, or pick a sample at the top.</li>
          <li className="flex gap-2"><Num n={2} /> Press <Kbd>Run &amp; visualize</Kbd> or <Kbd>Ctrl/⌘ + Enter</Kbd>.</li>
          <li className="flex gap-2"><Num n={3} /> Step with <Kbd>←</Kbd> <Kbd>→</Kbd>, or press <Kbd>Space</Kbd> to play.</li>
        </ol>
      </div>
    </div>
  );
}

export function RunningState() {
  return (
    <div className="flex h-full items-center justify-center gap-2 text-[13px] text-slate-400" role="status">
      <Spinner /> Running your program in an isolated process…
    </div>
  );
}

export function NotRunState({ message }: { message: string }) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-sm rounded-lg border border-rose-400/30 bg-rose-500/[0.06] p-4 text-center text-[13px] text-rose-100">
        <p className="font-semibold">The program could not be visualized</p>
        <p className="mt-1 text-rose-200/80">{message}</p>
        <p className="mt-2 text-xs text-slate-400">Fix the highlighted line in the editor and run again.</p>
      </div>
    </div>
  );
}

function Num({ n }: { n: number }) {
  return <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ink-700 text-[11px] font-semibold text-slate-300">{n}</span>;
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border border-ink-500 bg-ink-800 px-1 py-px font-mono text-[11px] text-slate-200">{children}</kbd>;
}
