import { useMemo, useRef } from 'react';
import type { Frame, Step, Value } from '../types/trace';
import { heapChangeFor, orderedHeapIds, previewValue, referrers, valueType, variableChange } from '../lib/trace-utils';
import { ArrowLayer } from './ArrowLayer';
import { CHANGE_ROW_BG, ChangeBadge } from './ChangeBadge';
import { HeapObjectView } from './HeapObjectView';
import { InfoTip } from './Tooltip';
import { PRIM_COLORS, Pointer, ValueTransition } from './ValueView';

interface Props {
  step: Step;
  prevStep?: Step;
  stepKey: number;
}

export function MemoryView({ step, prevStep, stepKey }: Props) {
  const contentRef = useRef<HTMLDivElement>(null);
  const heapIds = useMemo(() => orderedHeapIds(step), [step]);
  const refs = useMemo(() => referrers(step), [step]);
  const prevHeap = prevStep?.heap ?? {};

  return (
    <div className="h-full overflow-auto" data-testid="memory-view">
      <div ref={contentRef} className="relative grid min-w-fit grid-cols-1 gap-x-14 gap-y-6 p-4 sm:grid-cols-[minmax(13rem,auto)_minmax(14rem,1fr)]">
        <section aria-label="Frames">
          <h3 className="mb-2 flex items-center text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Frames
            <InfoTip term="a frame">
              A <b>frame</b> is the workspace of one running function: it holds that call's local variables. The
              <b> global frame</b> holds variables created outside any function. Each new call adds a frame; returning removes it.
            </InfoTip>
          </h3>
          <div className="flex flex-col gap-3">
            {step.stack.map((frame) => (
              <FrameCard key={frame.id} frame={frame} step={step} prevStep={prevStep} stepKey={stepKey} />
            ))}
          </div>
        </section>
        <section aria-label="Objects">
          <h3 className="mb-2 flex items-center text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Objects
            <InfoTip term="an object reference">
              Lists, dictionaries, sets, tuples and functions live here as <b>objects</b>. A variable does not contain the list
              itself; it holds a <b>reference</b> (the arrow). Two arrows to one box mean two names share the same object, so a
              change made through one name is visible through the other.
            </InfoTip>
          </h3>
          {heapIds.length === 0 ? (
            <p className="max-w-[16rem] text-xs leading-relaxed text-slate-500">
              No objects yet. Numbers, strings, booleans and None are shown directly inside the variables.
            </p>
          ) : (
            <div className="flex flex-col items-start gap-3">
              {heapIds.map((id) => (
                <HeapObjectView
                  key={id}
                  obj={step.heap[id]}
                  heap={step.heap}
                  change={heapChangeFor(step, id)}
                  referrers={refs.get(id) ?? []}
                  stepKey={stepKey}
                  isNew={!!prevStep && !prevHeap[id]}
                />
              ))}
            </div>
          )}
        </section>
        <ArrowLayer container={contentRef} version={`${stepKey}-${heapIds.length}`} />
      </div>
    </div>
  );
}

function FrameCard({ frame, step, prevStep, stepKey }: { frame: Frame; step: Step; prevStep?: Step; stepKey: number }) {
  const active = frame.id === step.frameId;
  const removed = step.changes.filter((c) => c.frameId === frame.id && c.kind === 'removed');
  return (
    <div
      className={`min-w-[13rem] rounded-lg border bg-ink-850 ${
        active ? 'border-sky-400/60 shadow-[0_0_0_1px_rgba(56,189,248,0.15)]' : 'border-ink-600'
      }`}
      data-testid={`frame-${frame.id}`}
    >
      <div className="flex items-center gap-2 border-b border-ink-700 px-3 py-1.5">
        <span className={`text-[13px] font-semibold ${frame.isGlobal ? 'text-slate-200' : 'text-sky-200'}`}>
          {frame.isGlobal ? 'Global frame' : `${frame.name}()`}
        </span>
        {frame.line != null && <span className="text-[11px] text-slate-500">line {frame.line}</span>}
        {active && <span className="ml-auto rounded bg-sky-400/10 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-sky-300">active</span>}
      </div>
      {frame.locals.length === 0 && !frame.returnValue && removed.length === 0 ? (
        <p className="px-3 py-2 text-xs italic text-slate-500">no variables yet</p>
      ) : (
        <ul className="divide-y divide-ink-700/70">
          {frame.locals.map((v) => {
            const change = variableChange(step, frame.id, v.name);
            return (
              <li
                key={`${v.name}-${change ? stepKey : 's'}`}
                className={`flex items-center gap-3 px-3 py-1.5 ${change ? CHANGE_ROW_BG[change.kind] : ''}`}
                data-testid={`var-${frame.id}-${v.name}`}
              >
                <span className="min-w-[3.5rem] font-mono text-[13px] text-slate-100">{v.name}</span>
                {change && v.value.kind === 'ref' && <ChangeBadge kind={change.kind} />}
                <span className="flex min-w-0 flex-1 items-center gap-2">
                  <VariableValue
                    value={v.value}
                    previous={change?.kind === 'rebound' ? change.before : null}
                    step={step}
                    prevStep={prevStep}
                    ptrId={`${frame.id}:${v.name}`}
                    active={!!change}
                    stepKey={stepKey}
                  />
                </span>
                {change && v.value.kind === 'prim' && <ChangeBadge kind={change.kind} />}
              </li>
            );
          })}
          {removed.map((c) => (
            <li key={`removed-${c.name}-${stepKey}`} className={`flex items-center gap-3 px-3 py-1.5 ${CHANGE_ROW_BG.removed}`}>
              <span className="min-w-[3.5rem] font-mono text-[13px] text-slate-500 line-through">{c.name}</span>
              <span className="flex-1 font-mono text-xs text-slate-600 line-through">
                {previewValue(c.before, prevStep?.heap ?? {}, 24)}
              </span>
              <ChangeBadge kind="removed" />
            </li>
          ))}
          {frame.returnValue && (
            <li className="flex items-center gap-3 bg-violet-400/[0.07] px-3 py-1.5">
              <span className="min-w-[3.5rem] text-[12px] font-semibold text-violet-300">Return value</span>
              <span className="flex-1">
                <VariableValue value={frame.returnValue} step={step} ptrId={`${frame.id}:<return>`} active stepKey={stepKey} />
              </span>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

interface ValueProps {
  value: Value;
  previous?: Value | null;
  step: Step;
  prevStep?: Step;
  ptrId: string;
  active: boolean;
  stepKey: number;
}

function VariableValue({ value, previous, step, prevStep, ptrId, active, stepKey }: ValueProps) {
  if (value.kind === 'ref') {
    return (
      <span className="flex flex-1 items-center justify-end gap-2">
        <span className="text-[11px] text-slate-500">{valueType(value, step.heap)}</span>
        <Pointer ptrId={ptrId} target={value.id} heap={step.heap} active={active} showLabel={false} />
      </span>
    );
  }
  const prevText = previous ? previewValue(previous, prevStep?.heap ?? {}, 24) : null;
  return (
    <span className="flex min-w-0 items-center gap-2">
      <ValueTransition text={value.repr} previous={prevText} animKey={stepKey} className={`font-mono text-[13px] ${PRIM_COLORS[value.type] ?? 'text-slate-200'}`} />
      <span className="shrink-0 text-[11px] text-slate-500">{valueType(value, step.heap)}</span>
    </span>
  );
}
