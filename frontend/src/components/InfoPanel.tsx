import { useEffect, useRef } from 'react';
import type { Step, TraceError, TraceResponse } from '../types/trace';
import { EVENT_LABELS, newOutputAt, outputAt } from '../lib/trace-utils';

export type InfoTab = 'explanation' | 'output' | 'errors';

interface Props {
  trace: TraceResponse | null;
  index: number;
  tab: InfoTab;
  onTab: (tab: InfoTab) => void;
  requestError: string | null;
  onJump: (index: number) => void;
  showConsolePreview: boolean;
}

const EVENT_STYLES: Record<Step['event'], string> = {
  line: 'bg-sky-400/10 text-sky-300 ring-sky-400/30',
  call: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/30',
  return: 'bg-violet-400/10 text-violet-300 ring-violet-400/30',
  exception: 'bg-rose-400/10 text-rose-300 ring-rose-400/30',
  finish: 'bg-slate-400/10 text-slate-300 ring-slate-400/30',
};

export function InfoPanel({ trace, index, tab, onTab, requestError, onJump, showConsolePreview }: Props) {
  const step = trace?.steps[index];
  const errorCount = (requestError ? 1 : 0) + (trace?.error ? 1 : 0);
  const output = trace ? outputAt(trace, step) : '';

  const tabs: { id: InfoTab; label: string; badge?: number }[] = [
    { id: 'explanation', label: 'Explanation' },
    { id: 'output', label: 'Output' },
    { id: 'errors', label: 'Errors', badge: errorCount },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div role="tablist" aria-label="Execution details" className="flex shrink-0 gap-1 border-b border-ink-700 px-2 pt-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => onTab(t.id)}
            className={`relative -mb-px flex items-center gap-1.5 rounded-t-md border px-3 py-1.5 text-[13px] font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 ${
              tab === t.id ? 'border-ink-700 border-b-ink-900 bg-ink-900 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {t.label}
            {!!t.badge && <span className="rounded-full bg-rose-500/20 px-1.5 text-[10px] font-semibold text-rose-300">{t.badge}</span>}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="min-h-0 flex-1 overflow-auto">
        {tab === 'explanation' && <ExplanationTab trace={trace} step={step} onShowErrors={() => onTab('errors')} />}
        {tab === 'output' && <OutputTab trace={trace} index={index} output={output} />}
        {tab === 'errors' && <ErrorsTab trace={trace} requestError={requestError} onJump={onJump} currentIndex={index} />}
      </div>
      {showConsolePreview && tab !== 'output' && trace && (
        <button
          type="button"
          onClick={() => onTab('output')}
          className="shrink-0 border-t border-ink-700 bg-ink-950/60 px-4 py-2 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-400"
          aria-label="Show full program output"
        >
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-slate-500">Output so far</span>
          <pre className="max-h-20 overflow-hidden whitespace-pre-wrap font-mono text-xs text-slate-300">
            {output ? lastLines(output, 4) : <span className="italic text-slate-600">nothing printed yet</span>}
          </pre>
        </button>
      )}
    </div>
  );
}

function lastLines(text: string, n: number): string {
  const lines = text.replace(/\n$/, '').split('\n');
  return lines.slice(-n).join('\n');
}

function ExplanationTab({ trace, step, onShowErrors }: { trace: TraceResponse | null; step?: Step; onShowErrors: () => void }) {
  if (!trace) {
    return (
      <div className="p-5 text-sm leading-relaxed text-slate-400">
        <p className="font-medium text-slate-300">Explanations appear here.</p>
        <p className="mt-1">After you run the program, each step is described in plain language, using the real values from the run.</p>
      </div>
    );
  }
  if (!step) {
    return (
      <div className="p-5 text-sm text-slate-400">
        The program did not run, so there are no steps to explain.{' '}
        {trace.error && (
          <button className="text-sky-300 underline underline-offset-2" onClick={onShowErrors}>
            See the error
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="p-4" aria-live="polite">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px]">
        <span className={`rounded px-1.5 py-0.5 font-semibold uppercase tracking-wide ring-1 ring-inset ${EVENT_STYLES[step.event]}`}>
          {EVENT_LABELS[step.event]}
        </span>
        {step.line != null && <span className="text-slate-400">line {step.line}</span>}
        {step.funcName && step.frameId !== 'global' && <span className="text-slate-400">in {step.funcName}()</span>}
        {step.condition && (
          <span className={`rounded px-1.5 py-0.5 font-mono ${step.condition.result ? 'bg-emerald-400/10 text-emerald-300' : 'bg-amber-400/10 text-amber-300'}`}>
            condition {step.condition.result ? 'True' : 'False'}
          </span>
        )}
        {step.loop && !step.loop.ended && (
          <span className="rounded bg-sky-400/10 px-1.5 py-0.5 text-sky-300">iteration {step.loop.iteration}</span>
        )}
      </div>
      <h2 key={step.index} className="animate-fade-in text-[15px] font-semibold leading-snug text-slate-100">{step.summary}</h2>
      <ol key={`b-${step.index}`} className="mt-3 flex animate-fade-in flex-col gap-1.5">
        {step.explanation.map((text, i) => (
          <li key={i} className="flex gap-2.5 text-[13.5px] leading-relaxed text-slate-300">
            <span className="mt-[3px] flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-ink-700 text-[10px] font-semibold text-slate-400">
              {i + 1}
            </span>
            <span>{text}</span>
          </li>
        ))}
      </ol>
      {step.exception && (
        <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/[0.07] p-3 text-[13px] text-rose-200">
          <span className="font-mono font-semibold">{step.exception.type}</span>: {step.exception.message}
          {step.exception.uncaught && <p className="mt-1 text-xs text-rose-300/80">The program stopped because this error was not handled.</p>}
        </div>
      )}
    </div>
  );
}

function OutputTab({ trace, index, output }: { trace: TraceResponse | null; index: number; output: string }) {
  const endRef = useRef<HTMLSpanElement>(null);
  const fresh = trace ? newOutputAt(trace, index) : '';
  const old = output.slice(0, output.length - fresh.length);
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [output]);
  if (!trace) return <p className="p-5 text-sm text-slate-400">Program output (from print) appears here as the program runs.</p>;
  return (
    <div className="p-4">
      {output ? (
        <pre data-testid="program-output" className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-slate-200">
          {old}
          {fresh && <span className="rounded-sm bg-sky-400/15 text-sky-100 animate-fade-in">{fresh}</span>}
          <span ref={endRef} />
        </pre>
      ) : (
        <p className="text-sm italic text-slate-500">Nothing has been printed yet at this step.</p>
      )}
    </div>
  );
}

const PHASE_TITLES: Record<TraceError['phase'], string> = {
  input: 'Nothing to run',
  syntax: 'Syntax error',
  unsupported: 'Not supported by the visualizer',
  runtime: 'Runtime error',
  limit: 'Execution limit reached',
  internal: 'Visualizer error',
};

function ErrorsTab({ trace, requestError, onJump, currentIndex }: { trace: TraceResponse | null; requestError: string | null; onJump: (i: number) => void; currentIndex: number }) {
  const exceptionSteps = trace?.steps.filter((s) => s.event === 'exception') ?? [];
  const error = trace?.error;
  if (!requestError && !error && exceptionSteps.length === 0) {
    return <p className="p-5 text-sm text-slate-400">{trace ? 'No errors. The program ran without problems.' : 'Errors and exceptions will be listed here.'}</p>;
  }
  return (
    <div className="flex flex-col gap-3 p-4 text-[13px]">
      {requestError && (
        <div role="alert" className="rounded-md border border-rose-400/40 bg-rose-500/[0.08] p-3 text-rose-100">
          <p className="font-semibold">Could not run the program</p>
          <p className="mt-1 text-rose-200/90">{requestError}</p>
        </div>
      )}
      {error && (
        <div role="alert" className={`rounded-md border p-3 ${error.phase === 'limit' ? 'border-amber-400/40 bg-amber-500/[0.07]' : 'border-rose-400/40 bg-rose-500/[0.08]'}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-wider ${error.phase === 'limit' ? 'text-amber-300' : 'text-rose-300'}`}>{PHASE_TITLES[error.phase]}</p>
          <p className="mt-1 font-mono text-slate-100">
            {error.type}: <span className="font-sans">{error.message}</span>
          </p>
          {error.line != null && <p className="mt-1 text-slate-400">Line {error.line}{error.column ? `, column ${error.column}` : ''}</p>}
          {error.hint && <p className="mt-2 leading-relaxed text-slate-300">{error.hint}</p>}
          {error.phase === 'runtime' && exceptionSteps.length > 0 && (
            <button
              type="button"
              onClick={() => onJump(exceptionSteps[exceptionSteps.length - 1].index)}
              className="mt-2 rounded border border-ink-500 px-2 py-1 text-xs text-slate-200 hover:border-sky-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
            >
              Go to the step where it happened
            </button>
          )}
          {trace?.truncated && trace.steps.length > 0 && <p className="mt-2 text-slate-400">The steps recorded before the limit are still available.</p>}
        </div>
      )}
      {exceptionSteps.some((s) => !s.exception?.uncaught) && (
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Handled exceptions</p>
          <ul className="flex flex-col gap-1">
            {exceptionSteps.filter((s) => !s.exception?.uncaught).map((s) => (
              <li key={s.index}>
                <button
                  type="button"
                  onClick={() => onJump(s.index)}
                  className={`w-full rounded px-2 py-1 text-left hover:bg-ink-800 ${s.index === currentIndex ? 'bg-ink-800' : ''}`}
                >
                  <span className="font-mono text-rose-200">{s.exception?.type}</span> <span className="text-slate-400">line {s.line}, step {s.index + 1} — caught by an except block</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
