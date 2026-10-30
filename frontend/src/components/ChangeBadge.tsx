import type { ChangeKind } from '../types/trace';
import { CHANGE_LABELS } from '../lib/trace-utils';

const STYLES: Record<ChangeKind, string> = {
  created: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/30',
  rebound: 'bg-amber-400/10 text-amber-300 ring-amber-400/30',
  mutated: 'bg-violet-400/10 text-violet-300 ring-violet-400/30',
  removed: 'bg-rose-400/10 text-rose-300 ring-rose-400/30',
};

const TITLES: Record<ChangeKind, string> = {
  created: 'This variable was created in this step.',
  rebound: 'This variable now refers to a different value (it was re-bound).',
  mutated: 'The object this variable refers to was modified in place; the variable still points to the same object.',
  removed: 'This variable was deleted in this step.',
};

export function ChangeBadge({ kind, detail }: { kind: ChangeKind; detail?: string }) {
  return (
    <span
      title={TITLES[kind]}
      className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset animate-fade-in ${STYLES[kind]}`}
    >
      {CHANGE_LABELS[kind]}
      {detail && <span className="font-mono font-normal normal-case tracking-normal opacity-80">{detail}</span>}
    </span>
  );
}

export const CHANGE_ROW_BG: Record<ChangeKind, string> = {
  created: 'bg-emerald-400/[0.06]',
  rebound: 'bg-amber-400/[0.06]',
  mutated: 'bg-violet-400/[0.06]',
  removed: 'bg-rose-400/[0.06]',
};
