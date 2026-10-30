import { useId, type ReactNode } from 'react';

interface Props {
  /** Short concept name, used for the accessible label. */
  term: string;
  children: ReactNode;
  align?: 'left' | 'right';
}

/** Small "?" button that explains an unfamiliar concept on hover or focus. */
export function InfoTip({ term, children, align = 'left' }: Props) {
  const id = useId();
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label={`What is ${term}?`}
        aria-describedby={id}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-ink-500 text-[10px] font-semibold leading-none text-slate-400 hover:border-sky-400 hover:text-sky-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
      >
        ?
      </button>
      <span
        role="tooltip"
        id={id}
        className={`pointer-events-none invisible absolute top-6 z-50 w-64 rounded-md border border-ink-600 bg-ink-800 px-3 py-2 text-xs font-normal normal-case leading-relaxed tracking-normal text-slate-200 opacity-0 shadow-xl transition-opacity duration-150 group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100 ${
          align === 'right' ? 'right-0' : 'left-0'
        }`}
      >
        {children}
      </span>
    </span>
  );
}
