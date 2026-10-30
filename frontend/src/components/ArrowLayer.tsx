import { useLayoutEffect, useState, type RefObject } from 'react';

interface Arrow {
  key: string;
  d: string;
  active: boolean;
}

interface Props {
  container: RefObject<HTMLElement>;
  /** Anything that changes when the DOM content changes (e.g. the step index). */
  version: unknown;
}

/**
 * Draws reference arrows on top of the memory view. Arrows are derived from
 * the DOM: every element with `data-ptr-target` gets an arrow to the element
 * with the matching `data-obj`. This keeps arrows exactly in sync with what
 * is rendered for the current snapshot.
 */
export function ArrowLayer({ container, version }: Props) {
  const [arrows, setArrows] = useState<Arrow[]>([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [layoutTick, setLayoutTick] = useState(0);

  useLayoutEffect(() => {
    const root = container.current;
    if (!root || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => setLayoutTick((t) => t + 1));
    observer.observe(root);
    return () => observer.disconnect();
  }, [container]);

  useLayoutEffect(() => {
    const root = container.current;
    if (!root) return;
    const base = root.getBoundingClientRect();
    const targets = new Map<string, DOMRect>();
    root.querySelectorAll<HTMLElement>('[data-obj]').forEach((el) => targets.set(el.dataset.obj!, el.getBoundingClientRect()));
    const next: Arrow[] = [];
    root.querySelectorAll<HTMLElement>('[data-ptr-target]').forEach((el) => {
      const target = targets.get(el.dataset.ptrTarget!);
      if (!target) return;
      const r = el.getBoundingClientRect();
      const x1 = r.left + r.width / 2 - base.left;
      const y1 = r.top + r.height / 2 - base.top;
      const ty = target.top - base.top + Math.min(18, target.height / 2);
      let d: string;
      const leftEdge = target.left - base.left;
      if (leftEdge > x1 + 24) {
        const dx = Math.max(30, (leftEdge - x1) * 0.45);
        d = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${leftEdge - dx} ${ty}, ${leftEdge - 2} ${ty}`;
      } else {
        // Target is not to the right (e.g. an object inside another object):
        // loop around and enter from the right edge.
        const rightEdge = target.right - base.left;
        const out = Math.max(x1, rightEdge) + 40;
        d = `M ${x1} ${y1} C ${out} ${y1}, ${out} ${ty}, ${rightEdge + 2} ${ty}`;
      }
      next.push({ key: el.dataset.ptr ?? `${next.length}`, d, active: el.dataset.ptrActive === 'true' });
    });
    setArrows(next);
    setSize({ w: root.scrollWidth, h: root.scrollHeight });
  }, [container, version, layoutTick]);

  return (
    <svg
      className="pointer-events-none absolute left-0 top-0 overflow-visible"
      width={size.w}
      height={size.h}
      aria-hidden="true"
      data-testid="arrow-layer"
    >
      <defs>
        <marker id="cv-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
        </marker>
        <marker id="cv-arrow-active" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
        </marker>
      </defs>
      {arrows.map((a) => (
        <path
          key={a.key}
          d={a.d}
          fill="none"
          stroke={a.active ? '#38bdf8' : '#64748b'}
          strokeWidth={a.active ? 2 : 1.5}
          strokeOpacity={a.active ? 0.95 : 0.7}
          markerEnd={`url(#${a.active ? 'cv-arrow-active' : 'cv-arrow'})`}
          className="transition-[d] duration-300"
        />
      ))}
    </svg>
  );
}
