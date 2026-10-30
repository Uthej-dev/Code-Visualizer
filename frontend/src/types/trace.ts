/**
 * Execution trace format produced by the backend tracer.
 * Mirrors backend/app/models.py — keep the two in sync.
 */

export interface PrimitiveValue {
  kind: 'prim';
  /** Python type name: int, float, str, bool, NoneType, complex, range */
  type: string;
  /** Python repr() of the value (possibly truncated). */
  repr: string;
}

export interface RefValue {
  kind: 'ref';
  /** Stable object id, e.g. "o3"; identical across all steps of a trace. */
  id: string;
}

export type Value = PrimitiveValue | RefValue;

export interface DictEntry {
  key: Value;
  value: Value;
}

export type HeapObjectType =
  | 'list'
  | 'tuple'
  | 'set'
  | 'frozenset'
  | 'dict'
  | 'instance'
  | 'function'
  | 'class'
  | 'other';

export interface HeapObject {
  id: string;
  type: HeapObjectType;
  items?: Value[] | null;
  entries?: DictEntry[] | null;
  length?: number | null;
  truncated?: boolean | null;
  name?: string | null;
  params?: string[] | null;
  line?: number | null;
  className?: string | null;
  members?: string[] | null;
  typeName?: string | null;
  repr?: string | null;
}

export interface Variable {
  name: string;
  value: Value;
}

export interface Frame {
  id: string;
  name: string;
  line: number | null;
  isGlobal: boolean;
  depth: number;
  locals: Variable[];
  returnValue?: Value | null;
}

export type ChangeKind = 'created' | 'rebound' | 'mutated' | 'removed';

export interface VariableChange {
  frameId: string;
  name: string;
  kind: ChangeKind;
  before?: Value | null;
  after?: Value | null;
}

export interface HeapChange {
  id: string;
  kind: 'created' | 'mutated';
  /** Member keys: list/tuple index ("0"), or encoded key ("str:'a'") for dicts/sets/attributes. */
  changed: string[];
  added: string[];
  removed: string[];
}

export type StepEvent = 'line' | 'call' | 'return' | 'exception' | 'finish';

export interface Step {
  index: number;
  eventId: string;
  event: StepEvent;
  line: number | null;
  endLine: number | null;
  frameId: string;
  funcName: string;
  stack: Frame[];
  heap: Record<string, HeapObject>;
  /** Length of `TraceResponse.output` produced up to and including this step. */
  outputLength: number;
  changes: VariableChange[];
  heapChanges: HeapChange[];
  summary: string;
  explanation: string[];
  exception?: { type: string; message: string; line: number | null; uncaught: boolean } | null;
  condition?: { result: boolean } | null;
  loop?: { line: number; iteration: number; ended: boolean } | null;
}

export type ErrorPhase = 'input' | 'syntax' | 'unsupported' | 'runtime' | 'limit' | 'internal';

export interface TraceError {
  phase: ErrorPhase;
  type: string;
  message: string;
  line?: number | null;
  column?: number | null;
  hint?: string | null;
}

export interface TraceResponse {
  version: number;
  status: 'ok' | 'error' | 'limit' | 'internal';
  steps: Step[];
  output: string;
  error?: TraceError | null;
  truncated: boolean;
  limitReason?: string | null;
  limits: Record<string, number>;
  stats: { stepCount: number; durationMs: number; isolation?: string[] | null };
}

export interface Sample {
  id: string;
  title: string;
  description: string;
  concepts: string[];
  code: string;
}
