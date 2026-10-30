import type { Step } from '../types/trace';
import { InfoTip } from './Tooltip';

export function CallStack({ step }: { step: Step | undefined }) {
  const frames = step ? [...step.stack].reverse() : [];
  return (
    <section aria-label="Call stack" className="border-t border-ink-700 px-4 py-3">
      <h3 className="mb-2 flex items-center text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        Call stack
        <InfoTip term="the call stack" align="right">
          The <b>call stack</b> lists the functions that are currently running. The top one is running right now; each one
          below it is paused, waiting for the function above it to return.
        </InfoTip>
      </h3>
      {frames.length === 0 ? (
        <p className="text-xs text-slate-500">Empty until the program runs.</p>
      ) : (
        <ol className="flex flex-col gap-1">
          {frames.map((f, i) => (
            <li
              key={f.id}
              className={`flex items-center gap-2 rounded-md border px-2.5 py-1 text-[13px] ${
                i === 0 ? 'border-sky-400/50 bg-sky-400/[0.07] text-sky-100' : 'border-ink-700 bg-ink-850 text-slate-300'
              }`}
            >
              <span className="font-mono">{f.isGlobal ? '<module>' : `${f.name}()`}</span>
              {f.line != null && <span className="text-[11px] text-slate-500">line {f.line}</span>}
              <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-500">{i === 0 ? 'running' : 'waiting'}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
