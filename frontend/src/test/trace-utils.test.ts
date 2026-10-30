import { describe, expect, it } from 'vitest';
import { newOutputAt, outputAt, previewValue, referrers, valueType, variableHistory } from '../lib/trace-utils';
import type { Value } from '../types/trace';
import { FIXTURES } from './fixtures';

const { trace: listTrace } = FIXTURES.modifyList;
const { trace: factTrace } = FIXTURES.factorial;

function collectRefs(node: unknown, out: string[] = []): string[] {
  if (Array.isArray(node)) node.forEach((n) => collectRefs(n, out));
  else if (node && typeof node === 'object') {
    const obj = node as Record<string, unknown>;
    if (obj.kind === 'ref') out.push(obj.id as string);
    Object.values(obj).forEach((v) => collectRefs(v, out));
  }
  return out;
}

describe('snapshot consistency', () => {
  it.each([
    ['modify-list', listTrace],
    ['factorial', factTrace],
  ])('every reference in %s resolves inside its own step', (_name, trace) => {
    trace.steps.forEach((step, i) => {
      expect(step.index).toBe(i);
      for (const id of collectRefs(step.stack)) expect(step.heap[id], `step ${i} ref ${id}`).toBeDefined();
    });
  });

  it('output only grows from step to step', () => {
    const lengths = listTrace.steps.map((s) => s.outputLength);
    expect([...lengths].sort((a, b) => a - b)).toEqual(lengths);
    expect(outputAt(listTrace, listTrace.steps.at(-1))).toBe(listTrace.output);
  });
});

describe('output helpers', () => {
  it('slices output at a step and isolates what that step printed', () => {
    const printStep = listTrace.steps.findIndex((s) => s.line === 10);
    expect(outputAt(listTrace, listTrace.steps[printStep])).toBe('scores: [75, 90, 100]\n');
    expect(newOutputAt(listTrace, printStep)).toBe('scores: [75, 90, 100]\n');
    expect(newOutputAt(listTrace, printStep + 1)).toBe('backup: [75, 90, 100]\n');
    expect(outputAt(listTrace, listTrace.steps[0])).toBe('');
  });
});

describe('value helpers', () => {
  it('previews lists and reports types', () => {
    const step = listTrace.steps[0];
    const scores = step.stack[0].locals.find((v) => v.name === 'scores')!.value;
    expect(previewValue(scores, step.heap)).toBe('[70, 85, 90]');
    expect(valueType(scores, step.heap)).toBe('list');
    const prim: Value = { kind: 'prim', type: 'NoneType', repr: 'None' };
    expect(valueType(prim, {})).toBe('None');
  });

  it('finds every variable that shares an object', () => {
    const step = listTrace.steps.find((s) => s.line === 8)!;
    const shared = [...referrers(step).values()].find((names) => names.length > 1);
    expect(shared).toEqual(['scores', 'backup']);
  });
});

describe('variable history', () => {
  it('lists changes up to the current step only', () => {
    const atStep2 = variableHistory(listTrace, 1);
    expect(atStep2.map((e) => `${e.change.name}:${e.change.kind}`)).toEqual(['scores:created', 'backup:created']);
    const all = variableHistory(listTrace, listTrace.steps.length - 1);
    expect(all.some((e) => e.change.name === 'scores' && e.change.kind === 'mutated')).toBe(true);
    expect(all.some((e) => e.change.name === 'scores' && e.change.kind === 'rebound')).toBe(true);
  });

  it('records local variables of recursive calls', () => {
    const entries = variableHistory(factTrace, factTrace.steps.length - 1);
    expect(entries.filter((e) => e.change.name === 'n' && e.change.kind === 'created')).toHaveLength(4);
  });
});
