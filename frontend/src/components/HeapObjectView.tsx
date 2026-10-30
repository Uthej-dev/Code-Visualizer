import type { HeapChange, HeapObject, Value } from '../types/trace';
import { memberKey } from '../lib/trace-utils';
import { Pointer, PrimitiveText } from './ValueView';

interface Props {
  obj: HeapObject;
  heap: Record<string, HeapObject>;
  change?: HeapChange;
  referrers: string[];
  stepKey: number;
  isNew: boolean;
}

const TYPE_ACCENT: Record<string, string> = {
  list: 'text-sky-300',
  tuple: 'text-cyan-300',
  dict: 'text-violet-300',
  set: 'text-teal-300',
  frozenset: 'text-teal-300',
  instance: 'text-pink-300',
  function: 'text-amber-200',
  class: 'text-pink-200',
  other: 'text-slate-300',
};

function MemberValue({ value, heap, ptrId }: { value: Value; heap: Record<string, HeapObject>; ptrId: string }) {
  if (value.kind === 'prim') return <PrimitiveText value={value} className="text-[13px]" />;
  return <Pointer ptrId={ptrId} target={value.id} heap={heap} showLabel={false} />;
}

function cellState(key: string, change?: HeapChange): 'added' | 'changed' | null {
  if (!change || change.kind !== 'mutated') return null;
  if (change.added.includes(key)) return 'added';
  if (change.changed.includes(key)) return 'changed';
  return null;
}

const CELL_STATE = {
  added: 'ring-1 ring-inset ring-emerald-400/60 animate-flash',
  changed: 'ring-1 ring-inset ring-amber-400/60 animate-flash',
};

export function HeapObjectView({ obj, heap, change, referrers, stepKey, isNew }: Props) {
  const typeLabel =
    obj.type === 'instance' ? `${obj.className} object` : obj.type === 'other' ? obj.typeName ?? 'object' : obj.type;
  const mutated = change?.kind === 'mutated';
  const removedCount = change?.removed.length ?? 0;

  return (
    <div
      data-obj={obj.id}
      className={`relative w-fit max-w-full rounded-lg border bg-ink-850 shadow-sm transition-colors duration-300 ${
        mutated ? 'border-violet-400/50' : isNew ? 'border-emerald-400/40' : 'border-ink-600'
      }`}
    >
      <div className="flex items-center gap-2 border-b border-ink-700 px-2.5 py-1 text-[11px]">
        <span className={`font-semibold ${TYPE_ACCENT[obj.type] ?? 'text-slate-300'}`}>{typeLabel}</span>
        {typeof obj.length === 'number' && obj.type !== 'instance' && (
          <span className="text-slate-500">len {obj.length}</span>
        )}
        <span className="ml-auto font-mono text-slate-600" title="Object identity (stable across steps)">
          #{obj.id.slice(1)}
        </span>
      </div>
      <div className="px-2.5 py-2">
        <ObjectBody obj={obj} heap={heap} change={change} stepKey={stepKey} />
      </div>
      {(referrers.length > 1 || mutated || removedCount > 0) && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 border-t border-ink-700 px-2.5 py-1 text-[11px]">
          {referrers.length > 1 && (
            <span className="text-sky-300/90" title="Several variables refer to this same object">
              shared by {referrers.join(', ')}
            </span>
          )}
          {mutated && <span className="text-violet-300/90">modified in place</span>}
          {removedCount > 0 && <span className="text-rose-300/90">{removedCount} removed</span>}
        </div>
      )}
    </div>
  );
}

function ObjectBody({ obj, heap, change, stepKey }: { obj: HeapObject; heap: Record<string, HeapObject>; change?: HeapChange; stepKey: number }) {
  switch (obj.type) {
    case 'list':
    case 'tuple':
    case 'set':
    case 'frozenset': {
      const items = obj.items ?? [];
      if (items.length === 0) return <span className="text-xs italic text-slate-500">empty</span>;
      const indexed = obj.type === 'list' || obj.type === 'tuple';
      return (
        <div className="flex flex-wrap gap-0.5">
          {items.map((item, i) => {
            const key = memberKey(obj, i);
            const state = cellState(key, change);
            return (
              <div
                key={`${i}-${state ? stepKey : 's'}`}
                className={`flex min-w-[2.25rem] flex-col items-center rounded border border-ink-600 bg-ink-900 ${state ? CELL_STATE[state] : ''}`}
              >
                {indexed && <span className="w-full border-b border-ink-700 px-1 text-center font-mono text-[10px] text-slate-500">{i}</span>}
                <span className="flex min-h-[1.6rem] items-center px-1.5 py-0.5">
                  <MemberValue value={item} heap={heap} ptrId={`${obj.id}:${i}`} />
                </span>
              </div>
            );
          })}
          {obj.truncated && <span className="self-center px-1 text-xs text-slate-500">… {Number(obj.length) - items.length} more</span>}
        </div>
      );
    }
    case 'dict':
    case 'instance': {
      const entries = obj.entries ?? [];
      if (entries.length === 0) return <span className="text-xs italic text-slate-500">{obj.type === 'dict' ? 'empty' : 'no attributes'}</span>;
      return (
        <table className="border-separate border-spacing-0 text-[13px]">
          <tbody>
            {entries.map((entry, i) => {
              const state = cellState(memberKey(obj, i), change);
              return (
                <tr key={`${i}-${state ? stepKey : 's'}`} className={state ? CELL_STATE[state] : ''}>
                  <td className="border-b border-r border-ink-700 py-0.5 pl-1 pr-2 align-middle">
                    {obj.type === 'instance' && entry.key.kind === 'prim' ? (
                      <span className="font-mono text-slate-300">.{entry.key.repr.slice(1, -1)}</span>
                    ) : (
                      <MemberValue value={entry.key} heap={heap} ptrId={`${obj.id}:k${i}`} />
                    )}
                  </td>
                  <td className="border-b border-ink-700 py-0.5 pl-2 pr-1 align-middle">
                    <MemberValue value={entry.value} heap={heap} ptrId={`${obj.id}:v${i}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      );
    }
    case 'function':
      return (
        <span className="font-mono text-[13px] text-amber-100">
          <span className="text-violet-300">def</span> {obj.name}({(obj.params ?? []).join(', ')})
          {obj.line ? <span className="ml-2 text-[11px] text-slate-500">line {obj.line}</span> : null}
        </span>
      );
    case 'class':
      return (
        <span className="font-mono text-[13px] text-pink-100">
          <span className="text-violet-300">class</span> {obj.name}
          {obj.members && obj.members.length > 0 && <span className="block text-[11px] text-slate-500">{obj.members.join(', ')}</span>}
        </span>
      );
    default:
      return <span className="font-mono text-[13px] text-slate-300">{obj.repr}</span>;
  }
}
