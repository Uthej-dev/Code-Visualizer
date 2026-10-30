import { useCallback, useMemo, useReducer, useRef, useState } from 'react';
import { CodeEditor, type EditorErrorMarker, type EditorMarker } from './components/CodeEditor';
import { CallStack } from './components/CallStack';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Controls, SPEEDS } from './components/Controls';
import { MemoryEmptyState, NotRunState, RunningState } from './components/EmptyState';
import { HistoryView } from './components/HistoryView';
import { InfoPanel, type InfoTab } from './components/InfoPanel';
import { MemoryView } from './components/MemoryView';
import { TopBar } from './components/TopBar';
import { InfoTip } from './components/Tooltip';
import { VariablesTable } from './components/VariablesTable';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useMediaQuery } from './hooks/useMediaQuery';
import { usePlayback } from './hooks/usePlayback';
import { ApiError, fetchTrace } from './lib/api';
import { initialNav, navReducer } from './lib/navigation';
import { DEFAULT_SAMPLE, SAMPLES } from './lib/samples';
import type { TraceResponse } from './types/trace';

type MemoryTab = 'memory' | 'variables' | 'history';
type MobilePanel = 'code' | 'memory' | 'info';

export default function App() {
  const [code, setCode] = useState(DEFAULT_SAMPLE?.code ?? '');
  const [sampleId, setSampleId] = useState(DEFAULT_SAMPLE?.id ?? '');
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [nav, dispatch] = useReducer(navReducer, initialNav);
  const [speedMs, setSpeedMs] = useState(SPEEDS[1].ms);
  const [infoTab, setInfoTab] = useState<InfoTab>('explanation');
  const [memoryTab, setMemoryTab] = useState<MemoryTab>('memory');
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>('code');
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const requestRef = useRef<AbortController | null>(null);

  const steps = trace?.steps ?? [];
  const step = steps[nav.index];
  const prevStep = nav.index > 0 ? steps[nav.index - 1] : undefined;
  const hasSteps = steps.length > 0;

  const run = useCallback(async () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setRunning(true);
    setRequestError(null);
    try {
      const result = await fetchTrace(code, controller.signal);
      if (controller.signal.aborted) return;
      setTrace(result);
      dispatch({ type: 'load', total: result.steps.length });
      if (result.steps.length === 0 && result.error) setInfoTab('errors');
      else if (infoTab === 'errors') setInfoTab('explanation');
      if (!isDesktop) setMobilePanel(result.steps.length ? 'memory' : 'info');
    } catch (err) {
      if (controller.signal.aborted) return;
      setTrace(null);
      dispatch({ type: 'clear' });
      setRequestError(err instanceof ApiError ? err.message : 'Something went wrong while running the program.');
      setInfoTab('errors');
      if (!isDesktop) setMobilePanel('info');
    } finally {
      if (requestRef.current === controller) setRunning(false);
    }
  }, [code, infoTab, isDesktop]);

  const reset = useCallback(() => {
    requestRef.current?.abort();
    setRunning(false);
    setTrace(null);
    setRequestError(null);
    dispatch({ type: 'clear' });
    setInfoTab('explanation');
    if (!isDesktop) setMobilePanel('code');
  }, [isDesktop]);

  const onCodeChange = useCallback(
    (value: string) => {
      setCode(value);
      // The trace describes the code that was run; once the code changes it no
      // longer applies, so return to editing mode instead of showing stale state.
      if (trace) {
        setTrace(null);
        dispatch({ type: 'clear' });
      }
    },
    [trace],
  );

  const loadSample = (id: string) => {
    const sample = SAMPLES.find((s) => s.id === id);
    if (!sample) return;
    setSampleId(id);
    setCode(sample.code);
    reset();
  };

  const tick = useCallback(() => dispatch({ type: 'tick' }), []);
  usePlayback(nav.playing, speedMs, tick);

  const handlers = useMemo(
    () => ({
      prev: () => dispatch({ type: 'prev' }),
      next: () => dispatch({ type: 'next' }),
      first: () => dispatch({ type: 'first' }),
      last: () => dispatch({ type: 'last' }),
      togglePlay: () => dispatch({ type: 'toggle' }),
      run: () => void run(),
    }),
    [run],
  );
  useKeyboardShortcuts(handlers, hasSteps);
  const jump = useCallback((index: number) => dispatch({ type: 'jump', index }), []);

  // ---- editor markers -------------------------------------------------------
  const current: EditorMarker | null = step && step.line != null ? { line: step.line, endLine: step.endLine } : null;
  const nextStep = steps[nav.index + 1];
  const next: EditorMarker | null = nextStep && nextStep.line != null ? { line: nextStep.line } : null;
  let errorMarker: EditorErrorMarker | null = null;
  if (trace?.error && !hasSteps && trace.error.line) {
    errorMarker = { line: trace.error.line, column: trace.error.column, message: `${trace.error.type}: ${trace.error.message}` };
  } else if (step?.exception && step.line != null) {
    errorMarker = { line: step.line, message: `${step.exception.type}: ${step.exception.message}` };
  }

  // ---- panels ----------------------------------------------------------------
  const panelVisibility = (panel: MobilePanel) => (isDesktop || mobilePanel === panel ? 'flex' : 'hidden');

  let memoryContent: React.ReactNode;
  if (running) memoryContent = <RunningState />;
  else if (!trace) memoryContent = <MemoryEmptyState />;
  else if (!step) memoryContent = <NotRunState message={trace.error ? `${trace.error.type}: ${trace.error.message}` : 'No steps were recorded.'} />;
  else if (memoryTab === 'memory') memoryContent = <MemoryView step={step} prevStep={prevStep} stepKey={nav.index} />;
  else if (memoryTab === 'variables') memoryContent = <VariablesTable step={step} />;
  else memoryContent = <HistoryView trace={trace} index={nav.index} onJump={jump} />;

  return (
    <div className="flex h-screen flex-col bg-ink-950 text-slate-200">
      <TopBar
        samples={SAMPLES}
        sampleId={sampleId}
        onSample={loadSample}
        onRun={() => void run()}
        running={running}
        status={running ? 'running' : trace ? 'visualizing' : 'editing'}
      />

      {!isDesktop && (
        <nav className="flex shrink-0 gap-1 border-b border-ink-700 bg-ink-900 p-1.5" aria-label="Switch panel">
          {(
            [
              ['code', 'Code'],
              ['memory', 'Memory'],
              ['info', 'Explain & output'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={mobilePanel === id}
              onClick={() => setMobilePanel(id)}
              className={`flex-1 rounded-md px-2 py-1.5 text-[13px] font-medium ${mobilePanel === id ? 'bg-ink-700 text-slate-100' : 'text-slate-400'}`}
            >
              {label}
            </button>
          ))}
        </nav>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-ink-700 lg:grid-cols-[minmax(0,37fr)_minmax(0,37fr)_minmax(0,26fr)]">
        {/* Panel A: code */}
        <section aria-label="Code editor" className={`${panelVisibility('code')} min-h-0 flex-col bg-ink-900`}>
          <PanelHeader title="Code">
            {trace && hasSteps ? (
              <span className="flex items-center gap-3 text-[11px] text-slate-400">
                <span className="flex items-center gap-1"><span className="cv-legend-current" /> just ran</span>
                <span className="flex items-center gap-1"><span className="cv-legend-next" /> runs next</span>
              </span>
            ) : (
              <span className="text-[11px] text-slate-500">editing · Python 3</span>
            )}
          </PanelHeader>
          {trace && hasSteps && (
            <p className="border-b border-ink-700 bg-sky-400/[0.05] px-4 py-1 text-[11px] text-sky-200/80">
              Visualizing a run of this code. Editing it will clear the visualization.
            </p>
          )}
          <div className="min-h-0 flex-1">
            <CodeEditor
              code={code}
              onChange={onCodeChange}
              onRun={() => void run()}
              current={current}
              next={next}
              error={errorMarker}
              stepKey={nav.index}
            />
          </div>
        </section>

        {/* Panel B: memory */}
        <section aria-label="Variables and memory" className={`${panelVisibility('memory')} min-h-0 flex-col bg-ink-900`}>
          <PanelHeader title="Memory">
            <div role="tablist" aria-label="Memory views" className="flex gap-1">
              {(
                [
                  ['memory', 'Diagram'],
                  ['variables', 'Variables'],
                  ['history', 'History'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={memoryTab === id}
                  onClick={() => setMemoryTab(id)}
                  className={`rounded px-2 py-0.5 text-[12px] font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 ${
                    memoryTab === id ? 'bg-ink-700 text-slate-100' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="hidden items-center gap-2 text-[11px] text-slate-500 xl:flex">
              <Legend color="bg-emerald-400" label="new" />
              <Legend color="bg-amber-400" label="changed" />
              <Legend color="bg-violet-400" label="modified" />
              <InfoTip term="changed vs. modified" align="right">
                <b>changed</b> (re-bound): the variable now points to a different value, e.g. <code>x = x + 1</code>.
                <br />
                <b>modified</b> (mutated): the variable still points to the same object, but the object's contents changed, e.g.{' '}
                <code>nums.append(4)</code>. Every name pointing to that object sees the change.
              </InfoTip>
            </span>
          </PanelHeader>
          <div className="min-h-0 flex-1">
            <ErrorBoundary resetKey={`${nav.index}-${memoryTab}-${trace ? 1 : 0}`}>{memoryContent}</ErrorBoundary>
          </div>
        </section>

        {/* Panel C: explanation, output, errors */}
        <section aria-label="Explanation and output" className={`${panelVisibility('info')} min-h-0 flex-col bg-ink-900`}>
          <div className="min-h-0 flex-1">
            <ErrorBoundary resetKey={`${nav.index}-${infoTab}`}>
            <InfoPanel
              trace={trace}
              index={nav.index}
              tab={infoTab}
              onTab={setInfoTab}
              requestError={requestError}
              onJump={jump}
              showConsolePreview={isDesktop}
            />
            </ErrorBoundary>
          </div>
          <CallStack step={step} />
        </section>
      </main>

      <footer className="shrink-0 border-t border-ink-700 bg-ink-900">
        <Controls
          nav={nav}
          steps={steps}
          speedMs={speedMs}
          onSpeed={setSpeedMs}
          onFirst={handlers.first}
          onPrev={handlers.prev}
          onNext={handlers.next}
          onLast={handlers.last}
          onToggle={handlers.togglePlay}
          onReset={reset}
          onJump={jump}
          disabled={!hasSteps || running}
        />
      </footer>
    </div>
  );
}

function PanelHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex h-10 shrink-0 items-center gap-3 border-b border-ink-700 px-4">
      <h2 className="text-[12px] font-semibold uppercase tracking-wider text-slate-400">{title}</h2>
      <div className="flex flex-1 items-center justify-between gap-3">{children}</div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={`h-2 w-2 rounded-sm ${color}`} />
      {label}
    </span>
  );
}
