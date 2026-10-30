const base = { width: 16, height: 16, viewBox: '0 0 16 16', fill: 'currentColor', 'aria-hidden': true } as const;

export const IconFirst = () => (
  <svg {...base}><path d="M3 3h1.6v10H3zM13 3.5v9L6 8z" /></svg>
);
export const IconPrev = () => (
  <svg {...base}><path d="M11.5 3.5v9L4.5 8z" /></svg>
);
export const IconNext = () => (
  <svg {...base}><path d="M4.5 3.5v9l7-4.5z" /></svg>
);
export const IconLast = () => (
  <svg {...base}><path d="M11.4 3H13v10h-1.6zM3 3.5v9L10 8z" /></svg>
);
export const IconPlay = () => (
  <svg {...base}><path d="M4.5 2.8v10.4L13 8z" /></svg>
);
export const IconPause = () => (
  <svg {...base}><path d="M4 3h3v10H4zM9 3h3v10H9z" /></svg>
);
export const IconReset = () => (
  <svg {...base} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 8a5 5 0 1 0 1.6-3.7" /><path d="M3 2.5v2.8h2.8" />
  </svg>
);
export const IconRun = () => (
  <svg {...base}><path d="M4 2.5v11L13.5 8z" /></svg>
);
export const Spinner = () => (
  <svg {...base} className="animate-spin" fill="none">
    <circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2" />
    <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);
