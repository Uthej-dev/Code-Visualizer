import type { HeapObject, Value } from '../types/trace';
import { previewValue, valueType } from '../lib/trace-utils';

export const PRIM_COLORS: Record<string, string> = {
  int: 'text-amber-300',
  float: 'text-amber-300',
  complex: 'text-amber-300',
  str: 'text-emerald-300',
  bool: 'text-violet-300',
  NoneType: 'text-slate-400 italic',
  range: 'text-sky-300',
};

interface PrimProps {
  value: Value & { kind: 'prim' };
  className?: string;
}

export function PrimitiveText({ value, className = '' }: PrimProps) {
  return (
    <span className={`font-mono ${PRIM_COLORS[value.type] ?? 'text-slate-200'} ${className}`} title={value.repr}>
      {value.repr}
    </span>
  );
}

interface PointerProps {
  /** Unique id of this pointer (used for drawing the arrow). */
  ptrId: string;
  target: string;
  heap: Record<string, HeapObject>;
  active?: boolean;
  showLabel?: boolean;
}

/** The tail of a reference arrow: a dot whose arrow is drawn by ArrowLayer. */
export function Pointer({ ptrId, target, heap, active = false, showLabel = true }: PointerProps) {
  const missing = !heap[target];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        data-ptr={ptrId}
        data-ptr-target={target}
        data-ptr-active={active ? 'true' : 'false'}
        aria-label={missing ? 'reference to an object not shown' : `reference to ${valueType({ kind: 'ref', id: target }, heap)} ${target}`}
        className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ring-2 ${
          active ? 'bg-sky-300 ring-sky-400/40' : 'bg-slate-300 ring-slate-400/20'
        }`}
      />
      {showLabel && (
        <span className="truncate font-mono text-xs text-slate-500">
          {missing ? 'not shown' : previewValue({ kind: 'ref', id: target }, heap, 28)}
        </span>
      )}
    </span>
  );
}

interface TransitionProps {
  text: string;
  previous?: string | null;
  animKey: number | string;
  className?: string;
}

/** Shows `text`, animating the previous value out when it changed. */
export function ValueTransition({ text, previous, animKey, className = '' }: TransitionProps) {
  const changed = previous != null && previous !== text;
  return (
    <span className="relative inline-flex min-w-0 max-w-full">
      {changed && (
        <span
          key={`old-${animKey}`}
          aria-hidden="true"
          className="pointer-events-none absolute left-0 top-0 whitespace-nowrap font-mono text-slate-500 line-through animate-value-out"
        >
          {previous}
        </span>
      )}
      <span key={`new-${animKey}`} className={`truncate ${changed ? 'animate-value-in' : ''} ${className}`}>
        {text}
      </span>
    </span>
  );
}
