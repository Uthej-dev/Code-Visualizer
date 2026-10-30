import { act, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { TraceResponse } from '../types/trace';
import { FIXTURES } from './fixtures';

// Monaco needs a real browser; replace it with a textarea that exposes the
// highlighted lines so tests can assert on them.
vi.mock('../components/CodeEditor', () => ({
  CodeEditor: (props: { code: string; onChange: (v: string) => void; current: { line: number } | null; next: { line: number } | null; error: { line: number; message: string } | null }) => (
    <div>
      <textarea aria-label="Python code editor" value={props.code} onChange={(e) => props.onChange(e.target.value)} />
      <span data-testid="current-line">{props.current?.line ?? ''}</span>
      <span data-testid="next-line">{props.next?.line ?? ''}</span>
      <span data-testid="error-line">{props.error ? `${props.error.line}:${props.error.message}` : ''}</span>
    </div>
  ),
}));

import App from '../App';

function mockFetch(trace: TraceResponse | Error) {
  const fn = vi.fn(async () => {
    if (trace instanceof Error) throw trace;
    return new Response(JSON.stringify(trace), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

async function runTrace(trace: TraceResponse) {
  const fetchMock = mockFetch(trace);
  render(<App />);
  await userEvent.click(screen.getByRole('button', { name: /run & visualize/i }));
  await screen.findByText(new RegExp(`/ ${trace.steps.length}`));
  return fetchMock;
}

const indicator = () => screen.getByTestId('step-indicator').textContent ?? '';
const explanationTitle = () => screen.getByRole('tabpanel').querySelector('h2')?.textContent;

function globalVars() {
  const frame = screen.getByTestId('frame-global');
  return within(frame).queryAllByTestId(/^var-global-/).map((el) => el.getAttribute('data-testid')!.replace('var-global-', ''));
}

describe('App', () => {
  beforeEach(() => vi.useRealTimers());
  afterEach(() => vi.unstubAllGlobals());

  it('shows a helpful empty state and disabled controls before running', () => {
    mockFetch(FIXTURES.factorial.trace);
    render(<App />);
    expect(screen.getByText(/see your program's memory/i)).toBeInTheDocument();
    for (const name of ['First step', 'Previous step', 'Next step', 'Last step', 'Play']) {
      expect(screen.getByRole('button', { name })).toBeDisabled();
    }
    expect(indicator()).toContain('Step 0 / 0');
  });

  it('runs code through the API and renders the first step', async () => {
    const { trace, code } = FIXTURES.modifyList;
    const fetchMock = await runTrace(trace);
    expect(fetchMock).toHaveBeenCalledWith('/api/trace', expect.objectContaining({ method: 'POST' }));
    expect(indicator()).toContain(`Step 1 / ${trace.steps.length}`);
    expect(screen.getByTestId('current-line').textContent).toBe(String(trace.steps[0].line));
    expect(screen.getByTestId('next-line').textContent).toBe(String(trace.steps[1].line));
    expect(explanationTitle()).toBe(trace.steps[0].summary);
    expect(globalVars()).toEqual(['scores']);
    expect(code).toContain('scores');
  });

  it('Next and Previous restore the exact snapshot of each step', async () => {
    const { trace } = FIXTURES.modifyList;
    await runTrace(trace);
    const seen: { vars: string[]; title: string | null | undefined; line: string | null }[] = [];
    for (let i = 0; i < trace.steps.length; i++) {
      const step = trace.steps[i];
      expect(indicator()).toContain(`Step ${i + 1} /`);
      expect(globalVars()).toEqual(step.stack[0].locals.map((v) => v.name));
      expect(explanationTitle()).toBe(step.summary);
      seen.push({ vars: globalVars(), title: explanationTitle(), line: screen.getByTestId('current-line').textContent });
      if (i < trace.steps.length - 1) await userEvent.click(screen.getByRole('button', { name: 'Next step' }));
    }
    expect(screen.getByRole('button', { name: 'Next step' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Last step' })).toBeDisabled();
    for (let i = trace.steps.length - 1; i >= 0; i--) {
      expect(globalVars()).toEqual(seen[i].vars);
      expect(explanationTitle()).toBe(seen[i].title);
      expect(screen.getByTestId('current-line').textContent).toBe(seen[i].line);
      if (i > 0) await userEvent.click(screen.getByRole('button', { name: 'Previous step' }));
    }
    expect(screen.getByRole('button', { name: 'Previous step' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'First step' })).toBeDisabled();
  });

  it('jumps with the timeline slider and restores output for that step', async () => {
    const { trace } = FIXTURES.modifyList;
    await runTrace(trace);
    const slider = screen.getByRole('slider', { name: /timeline/i });
    await userEvent.click(screen.getByRole('tab', { name: 'Output' }));

    fireEvent.change(slider, { target: { value: String(trace.steps.length - 1) } });
    expect(indicator()).toContain(`Step ${trace.steps.length} /`);
    expect(screen.getByTestId('program-output').textContent).toBe(trace.output);

    const firstPrint = trace.steps.findIndex((s) => s.outputLength > 0);
    fireEvent.change(slider, { target: { value: String(firstPrint) } });
    expect(screen.getByTestId('program-output').textContent).toBe(trace.output.slice(0, trace.steps[firstPrint].outputLength));

    fireEvent.change(slider, { target: { value: '0' } });
    expect(screen.queryByTestId('program-output')).not.toBeInTheDocument();
  });

  it('supports keyboard shortcuts for next, previous, first and last', async () => {
    const { trace } = FIXTURES.factorial;
    await runTrace(trace);
    const user = userEvent.setup();
    (document.activeElement as HTMLElement | null)?.blur();
    await user.keyboard('{ArrowRight}{ArrowRight}');
    expect(indicator()).toContain('Step 3 /');
    await user.keyboard('{ArrowLeft}');
    expect(indicator()).toContain('Step 2 /');
    await user.keyboard('{End}');
    expect(indicator()).toContain(`Step ${trace.steps.length} /`);
    await user.keyboard('{Home}');
    expect(indicator()).toContain('Step 1 /');
  });

  it('plays automatically and stops at the last step', async () => {
    const { trace } = FIXTURES.modifyList;
    await runTrace(trace);
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(800 * 2 + 10));
    expect(indicator()).toContain('Step 3 /');
    act(() => vi.advanceTimersByTime(800 * trace.steps.length));
    expect(indicator()).toContain(`Step ${trace.steps.length} /`);
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    vi.useRealTimers();
  });

  it('shows the call stack growing during recursion', async () => {
    const { trace } = FIXTURES.factorial;
    await runTrace(trace);
    const deepest = trace.steps.reduce((best, s) => (s.stack.length > best.stack.length ? s : best));
    fireEvent.change(screen.getByRole('slider', { name: /timeline/i }), { target: { value: String(deepest.index) } });
    const stack = screen.getByRole('region', { name: 'Call stack' });
    expect(within(stack).getAllByRole('listitem')).toHaveLength(deepest.stack.length);
    expect(within(stack).getAllByText('factorial()')).toHaveLength(deepest.stack.length - 1);
  });

  it('highlights a runtime exception and explains it', async () => {
    const { trace } = FIXTURES.runtimeError;
    await runTrace(trace);
    await userEvent.click(screen.getByRole('button', { name: 'Last step' }));
    expect(screen.getByTestId('error-line').textContent).toBe(`${trace.error!.line}:IndexError: list index out of range`);
    expect(screen.getAllByText(/IndexError/).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('tab', { name: /errors/i }));
    expect(screen.getByRole('alert')).toHaveTextContent('Runtime error');
    await userEvent.click(screen.getByRole('button', { name: 'First step' }));
    await userEvent.click(screen.getByRole('button', { name: /go to the step where it happened/i }));
    expect(indicator()).toContain(`Step ${trace.steps.length} /`);
  });

  it('reports syntax errors without inventing any steps', async () => {
    const { trace } = FIXTURES.syntaxError;
    mockFetch(trace);
    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /run & visualize/i }));
    expect(await screen.findByText(/could not be visualized/i)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Syntax error');
    expect(screen.getByTestId('error-line').textContent).toMatch(/^2:/);
    expect(screen.getByRole('button', { name: 'Next step' })).toBeDisabled();
  });

  it('shows a clear message when the server cannot be reached', async () => {
    mockFetch(new TypeError('Failed to fetch'));
    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /run & visualize/i }));
    expect(await screen.findByText(/could not reach the execution server/i)).toBeInTheDocument();
  });

  it('editing the code clears the stale visualization; Reset returns to editing', async () => {
    const { trace } = FIXTURES.modifyList;
    await runTrace(trace);
    await userEvent.type(screen.getByLabelText('Python code editor'), '#');
    expect(indicator()).toContain('Step 0 / 0');
    expect(screen.getByText(/see your program's memory/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /run again|run & visualize/i }));
    await screen.findByText(new RegExp(`/ ${trace.steps.length}`));
    await userEvent.click(screen.getByRole('button', { name: /reset/i }));
    expect(indicator()).toContain('Step 0 / 0');
  });

  it('survives browsers where scrollIntoView returns a Promise', async () => {
    // Recent Chrome returns a Promise from scrollIntoView; returning it from a
    // React effect used to crash the History and Output panels.
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = vi.fn(() => Promise.resolve()) as unknown as typeof original;
    try {
      const { trace } = FIXTURES.modifyList;
      await runTrace(trace);
      await userEvent.click(screen.getByRole('button', { name: 'Last step' }));
      await userEvent.click(screen.getByRole('tab', { name: 'History' }));
      expect(screen.getByRole('list', { name: /variable change history/i })).toBeInTheDocument();
      await userEvent.click(screen.getByRole('tab', { name: 'Output' }));
      expect(screen.getByTestId('program-output')).toHaveTextContent('backup still has');
    } finally {
      Element.prototype.scrollIntoView = original;
    }
  });

  it('loads sample programs into the editor', async () => {
    mockFetch(FIXTURES.factorial.trace);
    render(<App />);
    await userEvent.selectOptions(screen.getByLabelText(/load a sample program/i), 'factorial');
    expect((screen.getByLabelText('Python code editor') as HTMLTextAreaElement).value).toContain('def factorial');
  });
});
