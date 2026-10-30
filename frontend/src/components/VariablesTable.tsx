import type { Step } from '../types/trace';
import { previewValue, valueType, variableChange } from '../lib/trace-utils';
import { ChangeBadge } from './ChangeBadge';

export function VariablesTable({ step }: { step: Step }) {
  const rows = step.stack.flatMap((frame) =>
    frame.locals.map((v) => ({ frame, v, change: variableChange(step, frame.id, v.name) })),
  );
  const removed = step.changes.filter((c) => c.kind === 'removed');
  if (rows.length === 0 && removed.length === 0) {
    return <p className="p-4 text-sm text-slate-500">No variables exist yet at this step.</p>;
  }
  return (
    <div className="h-full overflow-auto p-3">
      <table className="w-full text-left text-[13px]">
        <thead className="sticky top-0 bg-ink-900 text-[11px] uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-2 py-1.5 font-semibold">Name</th>
            <th className="px-2 py-1.5 font-semibold">Value</th>
            <th className="px-2 py-1.5 font-semibold">Type</th>
            <th className="px-2 py-1.5 font-semibold">Scope</th>
            <th className="px-2 py-1.5 font-semibold">This step</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-700/70">
          {rows.map(({ frame, v, change }) => (
            <tr key={`${frame.id}-${v.name}`} className={change ? 'bg-ink-800/60' : ''}>
              <td className="px-2 py-1.5 font-mono text-slate-100">{v.name}</td>
              <td className="max-w-[16rem] truncate px-2 py-1.5 font-mono text-slate-300" title={previewValue(v.value, step.heap, 200)}>
                {previewValue(v.value, step.heap, 40)}
              </td>
              <td className="px-2 py-1.5 text-slate-400">{valueType(v.value, step.heap)}</td>
              <td className="px-2 py-1.5 text-slate-400">{frame.isGlobal ? 'global' : `local · ${frame.name}`}</td>
              <td className="px-2 py-1.5">{change ? <ChangeBadge kind={change.kind} /> : <span className="text-slate-600">—</span>}</td>
            </tr>
          ))}
          {removed.map((c) => (
            <tr key={`removed-${c.frameId}-${c.name}`}>
              <td className="px-2 py-1.5 font-mono text-slate-500 line-through">{c.name}</td>
              <td className="px-2 py-1.5 text-slate-600">—</td>
              <td className="px-2 py-1.5 text-slate-600">—</td>
              <td className="px-2 py-1.5 text-slate-500">{c.frameId === 'global' ? 'global' : 'local'}</td>
              <td className="px-2 py-1.5"><ChangeBadge kind="removed" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
