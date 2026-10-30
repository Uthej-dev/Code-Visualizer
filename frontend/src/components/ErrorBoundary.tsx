import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Changing this value clears a previous error (e.g. the step index). */
  resetKey?: unknown;
}

interface State {
  error: Error | null;
}

/** Keeps a rendering fault in one panel from blanking the whole app. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Panel failed to render', error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="m-4 rounded-md border border-rose-400/30 bg-rose-500/[0.06] p-3 text-[13px] text-rose-200">
          This panel could not be displayed for this step. Try another step or run the program again.
        </div>
      );
    }
    return this.props.children;
  }
}
