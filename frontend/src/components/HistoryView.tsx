import { useEffect, useMemo, useRef } from 'react';
import type { TraceResponse } from '../types/trace';
import { variableHistory } from '../lib/trace-utils';
import { ChangeBadge } from './ChangeBadge';

interface Props {
  trace: TraceResponse;
  index: number;
  onJump: (index: number) => void;
}

/** Every variable change from the start of the program up to the current step. */
export function HistoryView({ trace, index, onJump }: Props) {
  const entries = useMemo(() => variableHistory(trace, index), [trace, index]);
  const endRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [entries.length]);

  if (entries.length === 0) return <p className="p-4 text-sm text-slate-500">No variable has changed yet.</p>;
  return (
    <ol className="h-full overflow-auto p-2 text-[13px]" aria-label="Variable change history">
      {entries.map((e, i) => (
        <li key={`${e.stepIndex}-${e.change.frameId}-${e.change.name}-${i}`} ref={i === entries.length - 1 ? endRef : undefined}>
          <button
            type="button"
            onClick={() => onJump(e.stepIndex)}
            className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-ink-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 ${
              e.stepIndex === index ? 'bg-ink-800/70' : ''
            }`}
            title={`Go to step ${e.stepIndex + 1}`}
          >
            <span className="w-14 shrink-0 font-mono text-[11px] text-slate-500">step {e.stepIndex + 1}</span>
            <span className="w-12 shrink-0 font-mono text-[11px] text-slate-500">{e.line ? `L${e.line}` : ''}</span>
            <span className="font-mono text-slate-100">{e.change.name}</span>
            {!e.change.frameId.startsWith('global') && <span className="text-[11px] text-slate-500">in {e.frameName}</span>}
            <span className="min-w-0 flex-1 truncate font-mono text-slate-400">
              {e.change.kind === 'rebound' && (
                <>
                  <span className="text-slate-500 line-through">{e.before}</span> → <span className="text-slate-200">{e.after}</span>
                </>
              )}
              {(e.change.kind === 'created' || e.change.kind === 'mutated') && <span className="text-slate-300">{e.after}</span>}
            </span>
            <ChangeBadge kind={e.change.kind} />
          </button>
        </li>
      ))}
    </ol>
  );
}
