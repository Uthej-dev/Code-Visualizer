import type { HeapChange, HeapObject, Step, TraceResponse, Value, VariableChange } from '../types/trace';

export const TYPE_LABELS: Record<string, string> = {
  int: 'int',
  float: 'float',
  str: 'str',
  bool: 'bool',
  NoneType: 'None',
  complex: 'complex',
  range: 'range',
  list: 'list',
  tuple: 'tuple',
  dict: 'dict',
  set: 'set',
  frozenset: 'frozenset',
  function: 'function',
  class: 'class',
  instance: 'object',
  other: 'object',
};

/** Python-ish type name of a value as displayed to the user. */
export function valueType(value: Value, heap: Record<string, HeapObject>): string {
  if (value.kind === 'prim') return TYPE_LABELS[value.type] ?? value.type;
  const obj = heap[value.id];
  if (!obj) return 'object';
  if (obj.type === 'instance') return obj.className ?? 'object';
  if (obj.type === 'other') return obj.typeName ?? 'object';
  return TYPE_LABELS[obj.type] ?? obj.type;
}

/** Short one-line preview of a value, e.g. `[1, 2, 3]` or `{'a': 1}`. */
export function previewValue(value: Value | null | undefined, heap: Record<string, HeapObject>, limit = 48, depth = 0): string {
  if (!value) return '—';
  if (value.kind === 'prim') return clip(value.repr, limit);
  const obj = heap[value.id];
  if (!obj) return '…';
  if (depth > 1) return '…';
  const inner = (v: Value) => previewValue(v, heap, limit, depth + 1);
  let text: string;
  switch (obj.type) {
    case 'list':
      text = `[${(obj.items ?? []).map(inner).join(', ')}${obj.truncated ? ', …' : ''}]`;
      break;
    case 'tuple': {
      const items = (obj.items ?? []).map(inner);
      text = `(${items.join(', ')}${items.length === 1 ? ',' : ''})`;
      break;
    }
    case 'set':
    case 'frozenset':
      text = obj.items && obj.items.length ? `{${obj.items.map(inner).join(', ')}}` : 'set()';
      break;
    case 'dict':
      text = `{${(obj.entries ?? []).map((e) => `${inner(e.key)}: ${inner(e.value)}`).join(', ')}}`;
      break;
    case 'function':
      text = `${obj.name}(${(obj.params ?? []).join(', ')})`;
      break;
    case 'class':
      text = `class ${obj.name}`;
      break;
    case 'instance':
      text = `${obj.className} object`;
      break;
    default:
      text = obj.repr ?? 'object';
  }
  return clip(text, limit);
}

export function clip(text: string, limit: number): string {
  return text.length > limit ? text.slice(0, limit - 1) + '…' : text;
}

/** Key used by the backend diff for a member of a heap object. */
export function memberKey(obj: HeapObject, index: number): string {
  if (obj.type === 'list' || obj.type === 'tuple') return String(index);
  const v = obj.type === 'set' || obj.type === 'frozenset' ? obj.items?.[index] : obj.entries?.[index]?.key;
  if (!v) return '';
  return v.kind === 'ref' ? `@${v.id}` : `${v.type}:${v.repr}`;
}

export function heapChangeFor(step: Step | undefined, id: string): HeapChange | undefined {
  return step?.heapChanges.find((h) => h.id === id);
}

export function variableChange(step: Step | undefined, frameId: string, name: string): VariableChange | undefined {
  return step?.changes.find((c) => c.frameId === frameId && c.name === name);
}

/** Output text visible at a given step. */
export function outputAt(trace: TraceResponse, step: Step | undefined): string {
  return step ? trace.output.slice(0, step.outputLength) : '';
}

/** Output printed during exactly this step. */
export function newOutputAt(trace: TraceResponse, index: number): string {
  const step = trace.steps[index];
  if (!step) return '';
  const before = index > 0 ? trace.steps[index - 1].outputLength : 0;
  return trace.output.slice(before, step.outputLength);
}

export interface HistoryEntry {
  stepIndex: number;
  line: number | null;
  frameName: string;
  change: VariableChange;
  before: string;
  after: string;
}

/** All variable changes from the first step up to (and including) `upTo`. */
export function variableHistory(trace: TraceResponse, upTo: number): HistoryEntry[] {
  const entries: HistoryEntry[] = [];
  const last = Math.min(upTo, trace.steps.length - 1);
  for (let i = 0; i <= last; i++) {
    const step = trace.steps[i];
    const prevHeap = i > 0 ? trace.steps[i - 1].heap : {};
    for (const change of step.changes) {
      const frame = step.stack.find((f) => f.id === change.frameId);
      entries.push({
        stepIndex: i,
        line: step.line,
        frameName: frame?.name ?? change.frameId,
        change,
        before: change.before ? previewValue(change.before, prevHeap, 32) : '',
        after: change.after ? previewValue(change.after, step.heap, 32) : '',
      });
    }
  }
  return entries;
}

/** Ids of heap objects in stable display order (creation order). */
export function orderedHeapIds(step: Step): string[] {
  return Object.keys(step.heap).sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
}

/** Which variables (by frame and name) point at each heap object. */
export function referrers(step: Step): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const frame of step.stack) {
    for (const v of frame.locals) {
      if (v.value.kind !== 'ref') continue;
      const label = frame.isGlobal ? v.name : `${v.name} (${frame.name})`;
      map.set(v.value.id, [...(map.get(v.value.id) ?? []), label]);
    }
  }
  return map;
}

export const EVENT_LABELS: Record<Step['event'], string> = {
  line: 'Line ran',
  call: 'Function call',
  return: 'Return',
  exception: 'Exception',
  finish: 'Finished',
};

export const CHANGE_LABELS: Record<VariableChange['kind'], string> = {
  created: 'new',
  rebound: 'changed',
  mutated: 'modified',
  removed: 'deleted',
};
